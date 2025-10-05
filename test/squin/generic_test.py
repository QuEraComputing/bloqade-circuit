from bloqade import squin as sq


@sq.kernel
def test():
    q = sq.qubit.new(1)
    sq.reset(q[0])
    sq.x(q[0])


test.print()
