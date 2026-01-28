import math

import cirq
import numpy as np
import pytest

from bloqade.pyqrack import StackMemorySimulator
from bloqade.cirq_utils import load_circuit
from bloqade.cirq_utils.noise import (
    GeminiOneZoneNoiseModel,
    GeminiTwoZoneNoiseModel,
    GeminiOneZoneNoiseModelConflictGraphMoves,
    transform_circuit,
)


@pytest.mark.parametrize("scaling_factor", [0.0, 0.5, 1.0, 2.0])
def test_scaling_factor(scaling_factor: float):
    model_default = GeminiOneZoneNoiseModel()
    model_scaled = GeminiOneZoneNoiseModel(scaling_factor=scaling_factor)

    # Check that pauli_rates properties are scaled
    for prop in [
        "mover_pauli_rates",
        "sitter_pauli_rates",
        "global_pauli_rates",
        "local_pauli_rates",
        "cz_paired_pauli_rates",
        "cz_unpaired_pauli_rates",
    ]:
        default_rates = getattr(model_default, prop)
        scaled_rates = getattr(model_scaled, prop)
        for d, s in zip(default_rates, scaled_rates):
            assert np.isclose(s, d * scaling_factor), f"{prop} not scaled correctly"

    # Check that two_qubit_pauli error probabilities are scaled (excluding "II")
    default_probs = model_default.cz_paired_error_probabilities
    scaled_channel = model_scaled.two_qubit_pauli
    scaled_probs = scaled_channel.error_probabilities

    total_error_default = sum(p for k, p in default_probs.items() if k != "II")
    total_error_scaled = sum(p for k, p in scaled_probs.items() if k != "II")

    assert np.isclose(total_error_scaled, total_error_default * scaling_factor)
    assert np.isclose(scaled_probs.get("II", 0), 1.0 - total_error_scaled)


def create_ghz_circuit(qubits, measurements: bool = False):
    n = len(qubits)
    circuit = cirq.Circuit()

    # Step 1: Hadamard on the first qubit
    circuit.append(cirq.H(qubits[0]))

    # Step 2: CNOT chain from qubit i to i+1
    for i in range(n - 1):
        circuit.append(cirq.CNOT(qubits[i], qubits[i + 1]))
        if measurements:
            circuit.append(cirq.measure(qubits[i]))
            circuit.append(cirq.reset(qubits[i]))

    if measurements:
        circuit.append(cirq.measure(qubits[-1]))
        circuit.append(cirq.reset(qubits[-1]))

    return circuit


@pytest.mark.parametrize(
    "model,qubits,measurements",
    [
        (GeminiOneZoneNoiseModel(), None, False),
        (
            GeminiOneZoneNoiseModelConflictGraphMoves(),
            cirq.GridQubit.rect(rows=1, cols=2),
            False,
        ),
        (GeminiTwoZoneNoiseModel(), None, False),
        (GeminiOneZoneNoiseModel(), None, True),
        (
            GeminiOneZoneNoiseModelConflictGraphMoves(),
            cirq.GridQubit.rect(rows=1, cols=2),
            True,
        ),
        (GeminiTwoZoneNoiseModel(), None, True),
    ],
)
def test_simple_model(model: cirq.NoiseModel, qubits, measurements: bool):
    if qubits is None:
        qubits = cirq.LineQubit.range(2)

    circuit = create_ghz_circuit(qubits, measurements=measurements)

    with pytest.raises(ValueError):
        # make sure only native gate set is supported
        circuit.with_noise(model)

    # make sure the model works with with_noise so long as we have a native circuit
    native_circuit = cirq.optimize_for_target_gateset(
        circuit, gateset=cirq.CZTargetGateset()
    )
    native_circuit.with_noise(model)

    noisy_circuit = transform_circuit(circuit, model=model)

    cirq_sim = cirq.DensityMatrixSimulator()
    dm = cirq_sim.simulate(noisy_circuit).final_density_matrix
    pops_cirq = np.real(np.diag(dm))

    kernel = load_circuit(noisy_circuit)
    pyqrack_sim = StackMemorySimulator(
        min_qubits=2, rng_state=np.random.default_rng(1234)
    )

    pops_bloqade = [0.0] * 4

    nshots = 500
    for _ in range(nshots):
        ket = pyqrack_sim.state_vector(kernel)
        for i in range(4):
            pops_bloqade[i] += abs(ket[i]) ** 2 / nshots

    if measurements is True:
        for pops in (pops_bloqade, pops_cirq):
            assert math.isclose(pops[0], 1.0, abs_tol=1e-1)
            assert math.isclose(pops[3], 0.0, abs_tol=1e-1)
            assert math.isclose(pops[1], 0.0, abs_tol=1e-1)
            assert math.isclose(pops[2], 0.0, abs_tol=1e-1)

            assert pops[0] > 0.99
            assert pops[3] >= 0.0
            assert pops[1] >= 0.0
            assert pops[2] >= 0.0
    else:
        for pops in (pops_bloqade, pops_cirq):
            assert math.isclose(pops[0], 0.5, abs_tol=1e-1)
            assert math.isclose(pops[3], 0.5, abs_tol=1e-1)
            assert math.isclose(pops[1], 0.0, abs_tol=1e-1)
            assert math.isclose(pops[2], 0.0, abs_tol=1e-1)

            assert pops[0] < 0.5001
            assert pops[3] < 0.5001
            assert pops[1] >= 0.0
            assert pops[2] >= 0.0
