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
