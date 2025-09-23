from bloqade import squin

n = 2


@squin.kernel
def main():
    q = squin.qubit.new(n)
    squin.h(q[0])

    for i in range(n - 1):
        squin.cx(q[i], q[i + 1])


main.print()
