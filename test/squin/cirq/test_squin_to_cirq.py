import cirq

from bloqade import squin


def test_pauli():
    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        q2 = squin.qubit.new(4)
        x = squin.op.x()
        y = squin.op.y()
        z = squin.op.z()
        squin.qubit.apply(x, q[0])
        squin.qubit.apply(y, q2[0])
        squin.qubit.apply(z, q2[3])

    circuit = squin.cirq.emit_circuit(main)

    print(circuit)

    qbits = circuit.all_qubits()
    assert len(qbits) == 3
    assert isinstance(qbit := list(qbits)[-1], cirq.LineQubit)
    assert qbit.x == 5


def test_control():
    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        h = squin.op.h()
        squin.qubit.apply(h, q[0])
        cx = squin.op.cx()
        squin.qubit.apply(cx, q)

    main.print()

    circuit = squin.cirq.emit_circuit(main)

    print(circuit)

    assert len(circuit) == 2
    assert circuit[1].operations[0].gate == cirq.CNOT


test_control()
