import math

import pytest
from kirin.dialects import ilist

from bloqade import squin
from bloqade.pyqrack import PyQrack, PyQrackWire, PyQrackQubit, StackMemorySimulator


def test_qubit():
    @squin.kernel
    def new():
        return squin.qubit.new(3)

    new.print()

    target = PyQrack(
        3, pyqrack_options={"isBinaryDecisionTree": False, "isStabilizerHybrid": True}
    )
    result = target.run(new)
    assert isinstance(result, ilist.IList)
    assert isinstance(qubit := result[0], PyQrackQubit)

    out = qubit.sim_reg.out_ket()
    assert out == [1.0] + [0.0] * (2**3 - 1)

    @squin.kernel
    def m():
        q = squin.qubit.new(3)
        m = squin.qubit.measure(q)
        squin.qubit.apply(squin.op.reset(), q)
        return m

    target = PyQrack(3)
    result = target.run(m)
    assert isinstance(result, ilist.IList)
    assert result.data == [0, 0, 0]


def test_x():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        x = squin.op.x()
        squin.qubit.apply(x, q)
        return squin.qubit.measure(q[0])

    target = PyQrack(1)
    result = target.run(main)
    assert result == 1


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
        return squin.qubit.measure(q[1])

    target = PyQrack(2)
    result = target.run(main)
    assert result == 0

    @squin.kernel
    def main2():
        q = squin.qubit.new(2)
        x = squin.op.x()
        id = squin.op.identity(sites=1)
        cx = squin.op.control(x, n_controls=1)
        squin.qubit.apply(squin.op.kron(x, id), q)
        squin.qubit.apply(cx, q)
        return squin.qubit.measure(q[0])

    target = PyQrack(2)
    result = target.run(main2)
    assert result == 1

    @squin.kernel
    def main3():
        q = squin.qubit.new(2)
        x = squin.op.adjoint(squin.op.x())
        id = squin.op.identity(sites=1)
        cx = squin.op.control(x, n_controls=1)
        squin.qubit.apply(squin.op.kron(x, id), q)
        squin.qubit.apply(cx, q)
        return squin.qubit.measure(q[0])

    target = PyQrack(2)
    result = target.run(main3)
    assert result == 1


def test_cxx():
    @squin.kernel
    def main():
        q = squin.qubit.new(3)
        x = squin.op.x()
        cxx = squin.op.control(squin.op.kron(x, x), n_controls=1)
        squin.qubit.apply(x, [q[0]])
        squin.qubit.apply(cxx, q)
        return squin.qubit.measure(q)

    target = PyQrack(3)
    result = target.run(main)
    assert result == ilist.IList([1, 1, 1])


def test_mult():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        x = squin.op.x()
        id = squin.op.mult(x, x)
        squin.qubit.apply(id, q)
        return squin.qubit.measure(q[0])

    main.print()

    target = PyQrack(1)
    result = target.run(main)

    assert result == 0


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

    assert result == ilist.IList([1, 1])


def test_scale():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        x = squin.op.x()

        # TODO: replace by 2 * x once we have the rewrite
        s = squin.op.scale(x, 2)

        squin.qubit.apply(s, q)
        return squin.qubit.measure(q[0])

    target = PyQrack(1)
    result = target.run(main)
    assert result == 1


def test_phase():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        h = squin.op.h()
        squin.qubit.apply(h, q)

        p = squin.op.shift(math.pi)
        squin.qubit.apply(p, q)

        squin.qubit.apply(h, q)
        return squin.qubit.measure(q[0])

    target = PyQrack(1)
    result = target.run(main)
    assert result == 1


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
        return squin.qubit.measure(q[0])

    target = PyQrack(1)
    result = target.run(main2)
    assert result == 0


def test_adjoint():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        x = squin.op.x()
        xadj = squin.op.adjoint(x)
        squin.qubit.apply(xadj, q)
        return squin.qubit.measure(q[0])

    target = PyQrack(1)
    result = target.run(main)
    assert result == 1

    @squin.kernel
    def adj_that_does_something():
        q = squin.qubit.new(1)
        s = squin.op.s()
        sadj = squin.op.adjoint(s)
        h = squin.op.h()

        squin.qubit.apply(h, q)
        squin.qubit.apply(s, q)
        squin.qubit.apply(sadj, q)
        squin.qubit.apply(h, q)
        return squin.qubit.measure(q[0])

    target = PyQrack(1)
    result = target.run(adj_that_does_something)
    assert result == 0

    @squin.kernel
    def adj_of_adj():
        q = squin.qubit.new(1)
        s = squin.op.s()
        sadj = squin.op.adjoint(s)
        sadj_adj = squin.op.adjoint(sadj)
        h = squin.op.h()

        squin.qubit.apply(h, q)
        squin.qubit.apply(sadj, q)
        squin.qubit.apply(sadj_adj, q)
        squin.qubit.apply(h, q)
        return squin.qubit.measure(q[0])

    target = PyQrack(1)
    result = target.run(adj_of_adj)
    assert result == 0

    @squin.kernel
    def nested_adj():
        q = squin.qubit.new(1)
        s = squin.op.s()
        sadj = squin.op.adjoint(s)
        s_nested_adj = squin.op.adjoint(squin.op.adjoint(squin.op.adjoint(sadj)))

        h = squin.op.h()

        squin.qubit.apply(h, q)
        squin.qubit.apply(sadj, q)
        squin.qubit.apply(s_nested_adj, q)
        squin.qubit.apply(h, q)
        return squin.qubit.measure(q[0])

    target = PyQrack(1)
    result = target.run(nested_adj)
    assert result == 0


def test_rot():
    @squin.kernel
    def main_x():
        q = squin.qubit.new(1)
        x = squin.op.x()
        r = squin.op.rot(x, math.pi)
        squin.qubit.apply(r, q)
        return squin.qubit.measure(q[0])

    target = PyQrack(1)
    result = target.run(main_x)
    assert result == 1

    @squin.kernel
    def main_y():
        q = squin.qubit.new(1)
        y = squin.op.y()
        r = squin.op.rot(y, math.pi)
        squin.qubit.apply(r, q)
        return squin.qubit.measure(q[0])

    target = PyQrack(1)
    result = target.run(main_y)
    assert result == 1

    @squin.kernel
    def main_z():
        q = squin.qubit.new(1)
        z = squin.op.z()
        r = squin.op.rot(z, math.pi)
        squin.qubit.apply(r, q)
        return squin.qubit.measure(q[0])

    target = PyQrack(1)
    result = target.run(main_z)
    assert result == 0


def test_broadcast():
    @squin.kernel
    def main():
        q = squin.qubit.new(3)
        x = squin.op.x()
        squin.qubit.broadcast(x, q)
        return squin.qubit.measure(q)

    target = PyQrack(3)
    result = target.run(main)
    assert result == ilist.IList([1, 1, 1])

    @squin.kernel
    def multi_site_bc():
        q = squin.qubit.new(6)
        x = squin.op.x()

        # invert controls
        squin.qubit.apply(x, [q[0]])
        squin.qubit.apply(x, [q[1]])

        cx = squin.op.control(x, n_controls=2)
        squin.qubit.broadcast(cx, q)
        return squin.qubit.measure(q)

    target = PyQrack(6)
    result = target.run(multi_site_bc)
    assert result == ilist.IList([1, 1, 1, 0, 0, 0])

    @squin.kernel
    def bc_size_mismatch():
        q = squin.qubit.new(5)
        x = squin.op.x()

        # invert controls
        squin.qubit.apply(x, [q[0]])
        squin.qubit.apply(x, [q[1]])

        cx = squin.op.control(x, n_controls=2)
        squin.qubit.broadcast(cx, q)
        return squin.qubit.measure(q)

    target = PyQrack(5)

    with pytest.raises(RuntimeError):
        target.run(bc_size_mismatch)


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
    assert result == ilist.IList([0, 0, 0])


def test_projectors():
    @squin.kernel
    def main_p0():
        q = squin.qubit.new(1)
        h = squin.op.h()
        p0 = squin.op.p0()
        squin.qubit.apply(h, q)
        squin.qubit.apply(p0, q)
        return squin.qubit.measure(q[0])

    target = PyQrack(1)
    result = target.run(main_p0)
    assert result == 0

    @squin.kernel
    def main_p1():
        q = squin.qubit.new(1)
        h = squin.op.h()
        p1 = squin.op.p1()
        squin.qubit.apply(h, q)
        squin.qubit.apply(p1, q)
        return squin.qubit.measure(q[0])

    target = PyQrack(1)
    result = target.run(main_p1)
    assert result == 1


def test_pauli_str():
    @squin.kernel
    def main():
        q = squin.qubit.new(3)
        cstr = squin.op.pauli_string(string="XXX")
        squin.qubit.apply(cstr, q)
        return squin.qubit.measure(q)

    target = PyQrack(3)
    result = target.run(main)
    assert result == ilist.IList([1, 1, 1])


def test_identity():
    @squin.kernel
    def main():
        x = squin.op.x()
        q = squin.qubit.new(3)
        id = squin.op.identity(sites=2)
        squin.qubit.apply(squin.op.kron(x, id), q)
        return squin.qubit.measure(q)

    target = PyQrack(3)
    result = target.run(main)
    assert result == ilist.IList([1, 0, 0])


@pytest.mark.xfail
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


def test_reset():
    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        squin.qubit.broadcast(squin.op.h(), q)
        squin.qubit.broadcast(squin.op.reset(), q)
        squin.qubit.broadcast(squin.op.reset_to_one(), q)

    sim = StackMemorySimulator(min_qubits=2)
    ket = sim.state_vector(main)

    assert math.isclose(abs(ket[3]), 1, abs_tol=1e-6)
    assert ket[0] == ket[1] == ket[2] == 0
