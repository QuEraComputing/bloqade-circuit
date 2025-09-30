from bloqade import squin


@squin.kernel
def main():
    q = squin.qubit.new(3)
    squin.bit_flip(1.0, q[0])
    squin.single_qubit_pauli_channel(0.0, 1.0, 0.0, q[0])
    squin.qubit.measure(q)


main.print()
