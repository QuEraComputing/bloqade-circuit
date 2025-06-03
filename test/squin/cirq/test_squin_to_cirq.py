from bloqade import squin


@squin.kernel
def main():
    q = squin.qubit.new(2)
    q2 = squin.qubit.new(4)
    x = squin.op.x()
    squin.qubit.apply(x, q[0])
    squin.qubit.apply(x, q2[0])


main.print()

circuit = squin.cirq.emit_circuit(main)

print(circuit)
print(circuit.all_qubits())
