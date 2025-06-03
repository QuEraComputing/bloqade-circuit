from bloqade import squin


@squin.kernel
def main():
    q = squin.qubit.new(2)
    q2 = squin.qubit.new(4)
    x = squin.op.x()
    y = squin.op.y()
    squin.qubit.apply(x, q[0])
    squin.qubit.apply(y, q2[0])


main.print()

circuit = squin.cirq.emit_circuit(main)

print(circuit)
print(circuit.all_qubits())
