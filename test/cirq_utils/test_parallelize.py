import cirq
import pytest

from bloqade.cirq_utils import parallelize


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

    circuit2 = parallelize(circuit)
    assert len(circuit2.moments) == 7


@pytest.mark.parametrize(
    "n_qubits, depth, op_density, randon_state",
    [
        (4, 2, 0.5, 1),
        (4, 2, 0.5, 2),
        (4, 2, 0.5, 3),
        (4, 2, 0.5, 4),
        (5, 3, 0.5, 5),
        (5, 3, 0.5, 6),
        (5, 3, 0.5, 7),
        (5, 3, 0.5, 8),
        (6, 4, 0.5, 9),
        (6, 4, 0.5, 10),
        (6, 4, 0.5, 11),
        (6, 4, 0.5, 12),
        (7, 5, 0.5, 13),
        (7, 5, 0.5, 14),
        (7, 5, 0.5, 15),
        (7, 5, 0.5, 16),
        (7, 5, 0.5, 17),
    ],
)
def test_random_circuits(
    n_qubits: int, depth: int, op_density: float, randon_state: int
):
    from cirq.testing import random_circuit

    circuit = random_circuit(
        n_qubits,
        depth,
        op_density,
        random_state=randon_state,
    )

    parallelized_circuit = parallelize(circuit)
    state_vector = circuit.final_state_vector()
    parallelized_state_vector = parallelized_circuit.final_state_vector()
    try:
        assert cirq.allclose_up_to_global_phase(
            state_vector, parallelized_state_vector, atol=1e-8
        ), "State vectors do not match after parallelization"
    except AssertionError as e:
        print("Original Circuit:")
        print(circuit)
        print("Parallelized Circuit:")
        print(parallelized_circuit)
        raise e
