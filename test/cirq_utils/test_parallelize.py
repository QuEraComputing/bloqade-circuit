from itertools import product

import cirq
import numpy as np
import pytest

from bloqade.cirq_utils import (
    parallelize,
    remove_tags,
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
    circuit_b, _ = block_similarity(circuit, weight=1.0, block_id=1)
    circuit_m2 = remove_tags(circuit_m)
    circuit2 = parallelize(circuit)
    assert len(circuit2.moments) == 7

def test_measurement_and_reset():
    qubits = cirq.LineQubit.range(4)
    circuit = cirq.Circuit(
        cirq.H(qubits[0]),
        cirq.CX(qubits[0], qubits[1]),
        cirq.measure(qubits[1]),
        cirq.reset(qubits[1]),
        cirq.CX(qubits[1], qubits[2]),
        cirq.measure(qubits[2]),
        cirq.reset(qubits[2]),
        cirq.CX(qubits[2], qubits[3]),
        cirq.measure(qubits[0]),
        cirq.reset(qubits[0]),
    )

    circuit_m, _ = moment_similarity(circuit, weight=1.0)
    circuit_b, _ = block_similarity(circuit, weight=1.0, block_id=1)
    circuit_m2 = remove_tags(circuit_m)

    parallelized_circuit = parallelize(circuit)

    assert len(parallelized_circuit.moments) == 11

    #this circuit should deterministically return all qubits to |0>
    #let's check:
    simulator = cirq.Simulator()
    for _ in range(20): #one in a million chance we miss an error
        state_vector = simulator.simulate(parallelized_circuit).state_vector()
        assert np.all(np.isclose(np.abs(state_vector), np.concatenate((np.array([1]),np.zeros(2**4-1)))))

def test_nonunitary_error_gate():
    qubits = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(
        cirq.H(qubits[0]),
        cirq.CX(qubits[0], qubits[1]),
        cirq.amplitude_damp(0.5).on(qubits[1]),
        cirq.CX(qubits[1], qubits[0]),
    )

    parallelized_circuit = parallelize(circuit)

    assert len(parallelized_circuit.moments) == 7

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
