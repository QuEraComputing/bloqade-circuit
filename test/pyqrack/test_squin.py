import math

import pytest
from kirin.dialects import ilist

from bloqade import squin
from bloqade.pyqrack import PyQrack, PyQrackWire, PyQrackQubit


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
    def m():
        q = squin.qubit.new(3)
        m = squin.qubit.measure(q)
        squin.qubit.reset(q)
        return m

    target = PyQrack(3)
    result = target.run(m)
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


def test_kron():
    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        x = squin.op.x()
        k = squin.op.kron(x, x)
        squin.qubit.apply(k, q)
        return squin.qubit.measure(q)

    target = PyQrack(2)
    result = target.run(main)

    assert result == [1, 1]


def test_scale():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        x = squin.op.x()

        # TODO: replace by 2 * x once we have the rewrite
        s = squin.op.scale(x, 2)

        squin.qubit.apply(s, q)
        return squin.qubit.measure(q)

    target = PyQrack(1)
    result = target.run(main)
    assert result == [1]


def test_phase():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        h = squin.op.h()
        squin.qubit.apply(h, q)

        p = squin.op.shift(math.pi)
        squin.qubit.apply(p, q)

        squin.qubit.apply(h, q)
        return squin.qubit.measure(q)

    target = PyQrack(1)
    result = target.run(main)
    assert result == [1]


def test_sp():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        sp = squin.op.spin_p()
        squin.qubit.apply(sp, q)
        return q

    target = PyQrack(1)
    result = target.run(main)
    assert isinstance(result, ilist.IList)
    assert isinstance(qubit := result[0], PyQrackQubit)

    assert qubit.sim_reg.out_ket() == [0, 0]

    @squin.kernel
    def main2():
        q = squin.qubit.new(1)
        sn = squin.op.spin_n()
        sp = squin.op.spin_p()
        squin.qubit.apply(sn, q)
        squin.qubit.apply(sp, q)
        return squin.qubit.measure(q)

    target = PyQrack(1)
    result = target.run(main2)
    assert result == [0]


def test_adjoint():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        x = squin.op.x()
        xadj = squin.op.adjoint(x)
        squin.qubit.apply(xadj, q)
        return squin.qubit.measure(q)

    target = PyQrack(1)
    result = target.run(main)
    assert result == [1]


def test_rot():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        x = squin.op.x()
        r = squin.op.rot(x, math.pi)
        squin.qubit.apply(r, q)
        return squin.qubit.measure(q)

    target = PyQrack(1)
    result = target.run(main)
    assert result == [1]


def test_broadcast():
    @squin.kernel
    def main():
        q = squin.qubit.new(3)
        x = squin.op.x()
        squin.qubit.broadcast(x, q)
        return squin.qubit.measure(q)

    target = PyQrack(3)
    result = target.run(main)
    assert result == [1, 1, 1]

    @squin.kernel
    def non_bc_error():
        q = squin.qubit.new(3)
        x = squin.op.x()
        cx = squin.op.control(x, n_controls=2)
        squin.qubit.broadcast(cx, q)
        return q

    target = PyQrack(3)
    with pytest.raises(RuntimeError):
        target.run(non_bc_error)


def test_u3():
    @squin.kernel
    def broadcast_h():
        q = squin.qubit.new(3)

        # rotate around Y by pi/2, i.e. perform a hadamard
        u = squin.op.u(math.pi / 2.0, 0, 0)

        squin.qubit.broadcast(u, q)
        return q

    target = PyQrack(3)
    q = target.run(broadcast_h)

    assert isinstance(q, ilist.IList)
    assert isinstance(qubit := q[0], PyQrackQubit)

    out = qubit.sim_reg.out_ket()

    # remove global phase introduced by pyqrack
    phase = out[0] / abs(out[0])
    out = [ele / phase for ele in out]

    for element in out:
        assert math.isclose(element.real, 1 / math.sqrt(8), abs_tol=2.2e-7)
        assert math.isclose(element.imag, 0, abs_tol=2.2e-7)

    @squin.kernel
    def broadcast_adjoint():
        q = squin.qubit.new(3)

        # rotate around Y by pi/2, i.e. perform a hadamard
        u = squin.op.u(math.pi / 2.0, 0, 0)

        squin.qubit.broadcast(u, q)

        # rotate back down
        u_adj = squin.op.adjoint(u)
        squin.qubit.broadcast(u_adj, q)
        return squin.qubit.measure(q)

    target = PyQrack(3)
    result = target.run(broadcast_adjoint)
    assert result == [0, 0, 0]


def test_clifford_str():
    @squin.kernel
    def main():
        q = squin.qubit.new(3)
        cstr = squin.op.clifford_string(string="XXX")
        squin.qubit.apply(cstr, q)
        return squin.qubit.measure(q)

    target = PyQrack(3)
    result = target.run(main)
    assert result == [1, 1, 1]


def test_wire():
    @squin.wired
    def main():
        q = squin.qubit.new(1)
        w = squin.wire.unwrap(q[0])
        x = squin.op.x()
        squin.wire.apply(x, w)
        return w

    target = PyQrack(1)
    result = target.run(main)
    assert isinstance(result, PyQrackWire)
    assert result.qubit.sim_reg.out_ket() == [0, 1]


# TODO: remove
# test_qubit()
# test_x()
# test_basic_ops("x")
# test_cx()
# test_mult()
# test_kron()
# test_scale()
# for i in range(100):
#     test_phase()
# test_sp()
# test_adjoint()
# for i in range(100):
#     test_rot()
# for i in range(100):
#     test_broadcast()
# test_broadcast()
# test_u3()
# test_clifford_str()
# test_wire()
