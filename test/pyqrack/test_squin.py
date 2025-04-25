import math

import pytest
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


def test_x():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        x = squin.op.x()
        squin.qubit.apply(x, q)
        return squin.qubit.measure(q)

    target = PyQrack(1)
    result = target.run(main)
    assert result == [1]


@pytest.mark.parametrize(
    "op_name",
    [
        "x",
        "y",
        "z",
        "h",
        "s",
        "t",
    ],
)
def test_basic_ops(op_name: str):
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        op = getattr(squin.op, op_name)()
        squin.qubit.apply(op, q)
        return q

    target = PyQrack(1)
    result = target.run(main)
    assert isinstance(result, ilist.IList)
    assert isinstance(qubit := result[0], PyQrackQubit)

    ket = qubit.sim_reg.out_ket()
    n = sum([abs(k) ** 2 for k in ket])
    assert math.isclose(n, 1, abs_tol=1e-6)


def test_cx():
    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        x = squin.op.x()
        cx = squin.op.control(x, n_controls=1)
        squin.qubit.apply(cx, q)
        return q

    target = PyQrack(2)
    target.run(main)


def test_mult():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        x = squin.op.x()
        id = squin.op.mult(x, x)
        squin.qubit.apply(id, q)
        return squin.qubit.measure(q)

    main.print()

    target = PyQrack(1)
    result = target.run(main)

    assert result == [0]


# TODO: remove
# test_qubit()
# test_x()
# test_basic_ops("x")
# test_cx()
# test_mult()
