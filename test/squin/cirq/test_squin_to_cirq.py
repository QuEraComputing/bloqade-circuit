from bloqade import squin


@squin.kernel
def main():
    q = squin.qubit.new(2)
    x = squin.op.x()
    squin.qubit.apply(x, q[0])


main.print()

circuit = squin.cirq.emit_circuit(main)

print(circuit)
