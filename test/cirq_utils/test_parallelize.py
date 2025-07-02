from itertools import product

import cirq
import numpy as np
import pytest

from bloqade.cirq_utils import (
    parallelize,
    no_similarity,
    block_similarity,
    moment_similarity,
)


def test1():
    qubits = cirq.LineQubit.range(8)
    circuit = cirq.Circuit(
        cirq.H(qubits[0]),
        cirq.CX(qubits[0], qubits[1]),
        cirq.CX(qubits[0], qubits[2]),
        cirq.CX(qubits[1], qubits[3]),
        cirq.CX(qubits[0], qubits[4]),
        cirq.CX(qubits[1], qubits[5]),
        cirq.CX(qubits[2], qubits[6]),
        cirq.CX(qubits[3], qubits[7]),
    )

    circuit_m, _ = moment_similarity(circuit, weight=1.0)
    # print(circuit_m)
    circuit_b, _ = block_similarity(circuit, weight=1.0, block_id=1)
    circuit_m2 = no_similarity(circuit_m)
    print(circuit_m2)
    circuit2 = parallelize(circuit)
    # print(circuit2)
    assert len(circuit2.moments) == 7


RNG_STATE = np.random.RandomState(1902833)


@pytest.mark.parametrize(
    "n_qubits, depth, op_density",
    product(
        range(1, 10),  # n_qubits
        range(1, 10),  # depth
        [0.1, 0.5, 0.9],  # op_density
    ),
)
def test_random_circuits(n_qubits: int, depth: int, op_density: float):
    from cirq.testing import random_circuit

    circuit = random_circuit(
        n_qubits,
        depth,
        op_density,
        random_state=RNG_STATE,
    )

    try:
        parallelized_circuit = parallelize(circuit)
    except Exception as e:
        print("Original Circuit:")
        print(circuit)
        raise e

    state_vector = circuit.final_state_vector()
    parallelized_state_vector = parallelized_circuit.final_state_vector()
    try:
        assert cirq.equal_up_to_global_phase(
            state_vector, parallelized_state_vector, atol=1e-8
        ), "State vectors do not match after parallelization"
    except Exception as e:
        print("Original Circuit:")
        print(circuit)
        print("Parallelized Circuit:")
        print(parallelized_circuit)
        raise e
