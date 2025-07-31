import cirq

from bloqade import squin

q = cirq.LineQubit.range(3)
circuit = cirq.Circuit(
    cirq.Moment(
        cirq.X(q[0]),
        cirq.H(q[1]),
    ),
    cirq.Moment(
        cirq.X(q[2]),
    ),
)

kernel = squin.cirq.load_circuit(circuit)

kernel.print()


circuit2 = squin.cirq.emit_circuit(kernel)

print(circuit2)
