import warnings

import cirq
import numpy as np
from scipy.linalg import sqrtm

from bloqade.cirq_utils.noise import (
    GeminiOneZoneNoiseModelConflictGraphMoves,
    get_two_zoned_noisy_circ,
    transform_to_qasm_u_gates,
    optimize_circuit_to_cz_gate_set,
    transform_to_noisy_one_zone_circuit,
)

dsim = cirq.DensityMatrixSimulator(dtype=np.complex128)

max_num_qubits = 5


def create_On_ghz_circuit(n):
    qubits = cirq.LineQubit.range(n)
    circuit = cirq.Circuit()

    # Step 1: Hadamard on the first qubit
    circuit.append(cirq.H(qubits[0]))

    # Step 2: CNOT chain from qubit i to i+1
    for i in range(n - 1):
        circuit.append(cirq.CNOT(qubits[i], qubits[i + 1]))

    return circuit


def fidelity(rho: np.ndarray, sigma: np.ndarray) -> float:
    """
    Calculate the Uhlmann fidelity between two density matrices.

    Parameters:
        rho (np.ndarray): A valid density matrix (Hermitian, PSD, trace=1)
        sigma (np.ndarray): Another density matrix to compare with rho

    Returns:
        float: Fidelity value in [0, 1]
    """
    # Compute sqrt of rho
    sqrt_rho = sqrtm(rho)

    # Compute the product sqrt(rho) * sigma * sqrt(rho)
    intermmediate = sqrt_rho @ sigma @ sqrt_rho

    # Compute the sqrt of the intermediate result
    sqrt_product = sqrtm(intermmediate)

    # Take the trace and square it
    fidelity_value = np.trace(sqrt_product)
    return np.real(fidelity_value) ** 2


trans_circuits = transform_to_noisy_one_zone_circuit(create_On_ghz_circuit(4))
compressed_circuit = trans_circuits[0]
noisy_circuit = trans_circuits[1]

create_On_ghz_circuit(4)

fidelities = []
for n in range(2, max_num_qubits):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ghz_circuit = create_On_ghz_circuit(n)
        trans_circuits = transform_to_noisy_one_zone_circuit(ghz_circuit)
        compressed_circuit = trans_circuits[0]
        noisy_circuit = trans_circuits[1]

        rho_noiseless = dsim.simulate(compressed_circuit).final_density_matrix
        rho_noisy = dsim.simulate(noisy_circuit).final_density_matrix

        fidelities.append(fidelity(rho_noisy, rho_noiseless))
    print(f"Simulation complete for {n} qubit GHZ")

fidelities_On = fidelities


def ghz_log_depth_circuit(n_qubits: int) -> cirq.Circuit:
    qubits = cirq.LineQubit.range(n_qubits)
    circuit = cirq.Circuit()

    # Step 1: Start with a Hadamard on the first qubit
    circuit.append(cirq.H(qubits[0]))

    # Step 2: Apply CNOTs in log-depth tree structure
    targeted = 1
    while targeted < n_qubits:
        moment = cirq.Moment()
        for i in range(0, targeted):
            if targeted + i < n_qubits:
                moment += cirq.CNOT(qubits[i], qubits[targeted + i])
            else:
                break
        targeted += targeted
        circuit += moment

    return circuit


fidelities = []
for n in range(2, max_num_qubits):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ghz_circuit = ghz_log_depth_circuit(n)
        trans_circuits = transform_to_noisy_one_zone_circuit(ghz_circuit)
        compressed_circuit = trans_circuits[0]
        noisy_circuit = trans_circuits[1]

        rho_noiseless = dsim.simulate(compressed_circuit).final_density_matrix
        rho_noisy = dsim.simulate(noisy_circuit).final_density_matrix

        fidelities.append(fidelity(rho_noisy, rho_noiseless))
    print(f"Simulation complete for {n} qubit GHZ")

fidelities_Ologn = fidelities

circuit = optimize_circuit_to_cz_gate_set(create_On_ghz_circuit(4))
circuit = transform_to_qasm_u_gates(circuit)
noisy_circuit = get_two_zoned_noisy_circ(circuit)


fidelities = []
for n in range(2, max_num_qubits):
    circuit = optimize_circuit_to_cz_gate_set(create_On_ghz_circuit(n))
    circuit = transform_to_qasm_u_gates(circuit)
    noisy_circuit = get_two_zoned_noisy_circ(circuit)

    rho_noiseless = dsim.simulate(circuit).final_density_matrix
    rho_noisy = dsim.simulate(noisy_circuit).final_density_matrix

    fidelities.append(fidelity(rho_noisy, rho_noiseless))

fidelities_On_twozone = fidelities

fidelities = []
for n in range(2, max_num_qubits):
    circuit = optimize_circuit_to_cz_gate_set(ghz_log_depth_circuit(n))
    circuit = transform_to_qasm_u_gates(circuit)
    noisy_circuit = get_two_zoned_noisy_circ(circuit)

    rho_noiseless = dsim.simulate(circuit).final_density_matrix
    rho_noisy = dsim.simulate(noisy_circuit).final_density_matrix

    fidelities.append(fidelity(rho_noisy, rho_noiseless))

fidelities_Ologn_twozone = fidelities

model = GeminiOneZoneNoiseModelConflictGraphMoves()


fidelities = []
for n in range(2, max_num_qubits):
    side_length = (
        np.floor(np.sqrt(n) - 0.0001) + 1
    )  # putting the atoms in a square grid
    ghz_circuit = create_On_ghz_circuit(n).transform_qubits(
        lambda q: cirq.GridQubit(q.x % side_length, q.x // side_length)
    )  # we need to define a 2D geometry for the conflict graph to work
    trans_circuits = transform_to_noisy_one_zone_circuit(ghz_circuit, model=model)
    compressed_circuit = trans_circuits[0]
    noisy_circuit = trans_circuits[1]

    rho_noiseless = dsim.simulate(compressed_circuit).final_density_matrix
    rho_noisy = dsim.simulate(noisy_circuit).final_density_matrix

    fidelities.append(fidelity(rho_noisy, rho_noiseless))

fidelities_On_conflict = fidelities

fidelities = []
for n in range(2, max_num_qubits):
    side_length = (
        np.floor(np.sqrt(n) - 0.0001) + 1
    )  # putting the atoms in a square grid
    ghz_circuit = ghz_log_depth_circuit(n).transform_qubits(
        lambda q: cirq.GridQubit(q.x % side_length, q.x // side_length)
    )  # we need to define a 2D geometry for the conflict graph to work
    trans_circuits = transform_to_noisy_one_zone_circuit(ghz_circuit, model=model)
    compressed_circuit = trans_circuits[0]
    noisy_circuit = trans_circuits[1]

    rho_noiseless = dsim.simulate(compressed_circuit).final_density_matrix
    rho_noisy = dsim.simulate(noisy_circuit).final_density_matrix

    fidelities.append(fidelity(rho_noisy, rho_noiseless))

fidelities_Ologn_conflict = fidelities
