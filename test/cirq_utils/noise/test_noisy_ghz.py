import math
import warnings

import cirq
import numpy as np

# from Cython.Build.Cache import zip_ext
from scipy.linalg import sqrtm

from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator
from bloqade.cirq_utils.noise import transform_circuit
from bloqade.squin.noise.rewrite import RewriteNoiseStmts


def test_noisy_ghz():

    max_num_qubits = 4

    dsim = cirq.DensityMatrixSimulator(dtype=np.complex128)

    def create_On_ghz_circuit(n):
        qubits = cirq.LineQubit.range(n)
        circuit = cirq.Circuit()

        # Step 1: Hadamard on the first qubit
        circuit.append(
            cirq.PhasedXZGate(
                x_exponent=0.5, z_exponent=1, axis_phase_exponent=-0.5
            ).on(qubits[0])
        )

        # Step 2: CNOT chain from qubit i to i+1
        for i in range(n - 1):
            circuit.append(
                cirq.PhasedXZGate(
                    x_exponent=0.5, z_exponent=1, axis_phase_exponent=-0.5
                ).on(qubits[i + 1])
            )
            circuit.append(cirq.CZ(qubits[i], qubits[i + 1]))
            circuit.append(
                cirq.PhasedXZGate(
                    x_exponent=0.5, z_exponent=1, axis_phase_exponent=-0.5
                ).on(qubits[i + 1])
            )

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

    fidelities = []
    fidelities_squin = []
    for n in range(3, max_num_qubits):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ghz_circuit = create_On_ghz_circuit(n)
            noisy_circuit = transform_circuit(ghz_circuit, to_native_gateset=False)

            rho_noiseless = dsim.simulate(ghz_circuit).final_density_matrix
            rho_noisy = dsim.simulate(noisy_circuit).final_density_matrix

            fidelities.append(fidelity(rho_noisy, rho_noiseless))

            # do the same in squin
            kernel = squin.cirq.load_circuit(noisy_circuit)
            RewriteNoiseStmts(kernel.dialects)(kernel)
            sim = StackMemorySimulator(
                min_qubits=n, rng_state=np.random.default_rng(1234)
            )
            rho_squin = np.zeros((2**n, 2**n), dtype=np.complex128)
            nshots = 300
            for _ in range(nshots):
                ket = sim.state_vector(kernel)
                rho_squin += np.outer(ket, np.conj(ket)) / float(nshots)

            fidelities_squin.append(fidelity(rho_noisy, rho_squin))

    recorded_fidelities = [
        np.float64(0.9570156385514068),
    ]

    for idx, fid in enumerate(fidelities):
        assert math.isclose(fid, recorded_fidelities[idx], abs_tol=1e-5)

    for n, fid_squin in zip(range(2, max_num_qubits), fidelities_squin):
        # NOTE: higher fidelity requires larger nshots in order for this to converge
        # this gates harder for more qubits and takes a lot longer, which doesn't make sense for the test here
        assert math.isclose(fid_squin, 1, abs_tol=1e-2 * n)
