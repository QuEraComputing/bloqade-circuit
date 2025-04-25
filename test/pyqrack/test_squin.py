from kirin.dialects import ilist

from bloqade import squin
from bloqade.pyqrack import PyQrack, PyQrackQubit


def test_qubit():
    @squin.kernel
    def new():
        return squin.qubit.new(3)

    new.print()

    target = PyQrack(3)
    result = target.run(new)
    assert isinstance(result, ilist.IList)
    assert isinstance(qubit := result[0], PyQrackQubit)

    out = qubit.sim_reg.out_ket()
    assert out == [1.0] + [0.0] * (2**3 - 1)

    @squin.kernel
    def measure():
        q = squin.qubit.new(3)
        m = squin.qubit.measure(q)
        squin.qubit.reset(q)
        return m

    target = PyQrack(3)
    result = target.run(measure)
    assert isinstance(result, list)
    assert result == [0, 0, 0]

    @squin.kernel
    def measure_and_reset():
        q = squin.qubit.new(3)
        m = squin.qubit.measure_and_reset(q)
        return m

    target = PyQrack(3)
    result = target.run(measure_and_reset)
    assert isinstance(result, list)
    assert result == [0, 0, 0]


# @squin.kernel
# def main():
#     q = squin.qubit.new(3)
#     x = squin.op.x()
#     id = squin.op.identity(sites=2)

#     # FIXME? Should we have a method apply(x, q, idx)?
#     squin.qubit.apply(squin.op.kron(x, id), q)

#     return squin.qubit.measure(q)


# main.print()

# target = PyQrack(2)
# result = target.run(main)


if __name__ == "main":
    test_qubit()
