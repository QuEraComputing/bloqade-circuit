import math

import cirq
import numpy as np
import pytest

from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator
from bloqade.cirq_utils.noise import (
    GeminiOneZoneNoiseModel,
    GeminiTwoZoneNoiseModel,
    GeminiOneZoneNoiseModelConflictGraphMoves,
    transform_circuit,
)
from bloqade.squin.noise.rewrite import RewriteNoiseStmts


def create_ghz_circuit(qubits):
    n = len(qubits)
    circuit = cirq.Circuit()

    # Step 1: Hadamard on the first qubit
    circuit.append(cirq.H(qubits[0]))

    # Step 2: CNOT chain from qubit i to i+1
    for i in range(n - 1):
        circuit.append(cirq.CNOT(qubits[i], qubits[i + 1]))

    return circuit


@pytest.mark.parametrize(
    "model,qubits",
    [
        (GeminiOneZoneNoiseModel(), None),
        (
            GeminiOneZoneNoiseModelConflictGraphMoves(),
            cirq.GridQubit.rect(rows=1, cols=2),
        ),
        (GeminiTwoZoneNoiseModel(), None),
    ],
)
def test_simple_model(model: cirq.NoiseModel, qubits):
    if qubits is None:
        qubits = cirq.LineQubit.range(2)

    circuit = create_ghz_circuit(qubits)

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

    kernel = squin.cirq.load_circuit(noisy_circuit)
    RewriteNoiseStmts(kernel.dialects)(kernel)
    pyqrack_sim = StackMemorySimulator(
        min_qubits=2, rng_state=np.random.default_rng(1234)
    )

    pops_bloqade = [0.0] * 4

    nshots = 500
    for _ in range(nshots):
        ket = pyqrack_sim.state_vector(kernel)
        for i in range(4):
            pops_bloqade[i] += abs(ket[i]) ** 2 / nshots

    for pops in (pops_bloqade, pops_cirq):
        assert math.isclose(pops[0], 0.5, abs_tol=1e-1)
        assert math.isclose(pops[3], 0.5, abs_tol=1e-1)
        assert math.isclose(pops[1], 0.0, abs_tol=1e-1)
        assert math.isclose(pops[2], 0.0, abs_tol=1e-1)

        assert pops[0] < 0.5001
        assert pops[3] < 0.5001
        assert pops[1] >= 0.0
        assert pops[2] >= 0.0


test_simple_model(
    GeminiOneZoneNoiseModelConflictGraphMoves(), cirq.GridQubit.rect(rows=1, cols=2)
)
