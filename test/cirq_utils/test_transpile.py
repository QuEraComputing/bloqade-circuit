import cirq

from bloqade.cirq_utils import transpile


def test_transpile():
    q = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(cirq.H(q[0]), cirq.CX(q[0], q[1]))

    native_circuit = transpile(circuit)

    print(native_circuit)

    assert native_circuit.moments[0].operations[0].gate.x_exponent == 0.5, print(
        native_circuit
    )
