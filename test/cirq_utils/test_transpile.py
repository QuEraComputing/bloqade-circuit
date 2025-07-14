import cirq

from bloqade.cirq_utils import transpile
from bloqade.cirq_utils.noise import transform_circuit


def test_transpile():
    q = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(cirq.H(q[0]), cirq.CX(q[0], q[1]))

    transformed_circuit = transform_circuit(circuit)

    print(transformed_circuit)

    assert(1 == 2)

    # assert native_circuit.moments[0].operations[0].gate.x_exponent == -0.5, print(
    #     native_circuit
    # )
