import math

import cirq
import numpy as np

from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator
from bloqade.cirq_utils.noise import (
    GeminiOneZoneNoiseModel,
    transform_circuit,
)
from bloqade.squin.noise.rewrite import RewriteNoiseStmts


def create_ghz_circuit(n):
    qubits = cirq.LineQubit.range(n)
    circuit = cirq.Circuit()

    # Step 1: Hadamard on the first qubit
    circuit.append(cirq.H(qubits[0]))

    # Step 2: CNOT chain from qubit i to i+1
    for i in range(n - 1):
        circuit.append(cirq.CNOT(qubits[i], qubits[i + 1]))

    return circuit


def test_model_with_defaults():
    circuit = create_ghz_circuit(2)

    print(circuit)

    model = GeminiOneZoneNoiseModel()

    noisy_circuit = transform_circuit(circuit=circuit, model=model)

    print(noisy_circuit)

    assert len(noisy_circuit) > len(circuit)

    # Make sure we added at least one noise statement
    all_ops = [op for moment in noisy_circuit for op in moment.operations]
    assert any(
        [isinstance(op.gate, cirq.AsymmetricDepolarizingChannel) for op in all_ops]
    )
    assert any([isinstance(op.gate, cirq.DepolarizingChannel) for op in all_ops])

    # pipe it through squin to pyqrack
    kernel = squin.cirq.load_circuit(noisy_circuit)

    RewriteNoiseStmts(kernel.dialects)(kernel)

    sim = StackMemorySimulator(min_qubits=2, rng_state=np.random.default_rng(1234))
    pops = [0.0] * 4
    nshots = 300
    for _ in range(nshots):
        ket = sim.state_vector(kernel)
        for i in range(4):
            pops[i] += abs(ket[i]) ** 2 / nshots

    assert math.isclose(pops[1], 0, abs_tol=1e-1)
    assert math.isclose(pops[2], 0, abs_tol=1e-1)
    assert math.isclose(pops[0], 0.5, abs_tol=1e-1)
    assert math.isclose(pops[3], 0.5, abs_tol=1e-1)

    sim = cirq.DensityMatrixSimulator()
    rho = sim.simulate(noisy_circuit).final_density_matrix

    assert math.isclose(np.real(rho[0, 0]), 0.5, abs_tol=1e-1)
    assert math.isclose(np.real(rho[0, 3]), 0.5, abs_tol=1e-1)
    assert math.isclose(np.real(rho[3, 0]), 0.5, abs_tol=1e-1)
    assert math.isclose(np.real(rho[3, 3]), 0.5, abs_tol=1e-1)
