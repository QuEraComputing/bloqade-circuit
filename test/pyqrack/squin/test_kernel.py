import math

import numpy as np
import pytest
from kirin.dialects import ilist

from bloqade import squin
from bloqade.pyqrack import PyQrack, PyQrackQubit, StackMemorySimulator


def test_qubit():
    @squin.kernel
    def new():
        return squin.qalloc(3)

    new.print()

    target = PyQrack(
        3, pyqrack_options={"isBinaryDecisionTree": False, "isStabilizerHybrid": True}
    )
    result = target.run(new)
    assert isinstance(result, ilist.IList)
    assert isinstance(qubit := result[0], PyQrackQubit)

    out = qubit.sim_reg.out_ket()
    out = np.asarray(out)

    i = np.abs(out).argmax()
    out /= out[i] / np.abs(out[i])

    expected = np.zeros_like(out)
    expected[0] = 1.0

    assert np.allclose(out, expected, atol=2.2e-7)

    @squin.kernel
    def m():
        q = squin.qalloc(3)
        m = squin.qubit.measure(q)
        return m

    target = PyQrack(3)
    result = target.run(m)
    assert isinstance(result, ilist.IList)
    assert result.data == [0, 0, 0]


def test_x():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        squin.x(q[0])
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
        "sqrt_x",
        "sqrt_y",
        "sqrt_z",
    ],
)
def test_basic_ops(op_name: str):
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        getattr(squin, op_name)(q[0])
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
        squin.cx(q[0], q[1])
        return squin.qubit.measure(q[1])

    target = PyQrack(2)
    result = target.run(main)
    assert result == 0

    @squin.kernel
    def main2():
        q = squin.qubit.new(2)
        squin.x(q[0])
        squin.cx(q[0], q[1])
        return squin.qubit.measure(q[0])

    target = PyQrack(2)
    result = target.run(main2)
    assert result == 1


def test_rot():
    @squin.kernel
    def main_x():
        q = squin.qubit.new(1)
        squin.rx(math.pi, q[0])
        return squin.qubit.measure(q[0])

    target = PyQrack(1)
    result = target.run(main_x)
    assert result == 1

    @squin.kernel
    def main_y():
        q = squin.qubit.new(1)
        squin.ry(math.pi, q[0])
        return squin.qubit.measure(q[0])

    target = PyQrack(1)
    result = target.run(main_y)
    assert result == 1

    @squin.kernel
    def main_z():
        q = squin.qubit.new(1)
        squin.rz(math.pi, q[0])
        return squin.qubit.measure(q[0])

    target = PyQrack(1)
    result = target.run(main_z)
    assert result == 0


def test_u3():
    @squin.kernel
    def broadcast_h():
        q = squin.qalloc(3)

        # rotate around Y by pi/2, i.e. perform a hadamard
        squin.broadcast.u3(math.pi / 2.0, 0, 0, q)
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
        q = squin.qalloc(3)

        # rotate around Y by pi/2, i.e. perform a hadamard
        squin.u3(math.pi / 2.0, 0, 0, q[0])
        squin.u3(math.pi / 2.0, 0, 0, q[1])
        squin.u3(math.pi / 2.0, 0, 0, q[2])

        # rotate back down
        squin.broadcast.u3(-math.pi / 2.0, 0, 0, q)
        return squin.qubit.measure(q)

    target = PyQrack(3)
    result = target.run(broadcast_adjoint)
    assert result == ilist.IList([0, 0, 0])


@pytest.mark.xfail
def test_reset():
    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        squin.broadcast.h(q)
        squin.broadcast.reset(q)

    sim = StackMemorySimulator(min_qubits=2)
    ket = sim.state_vector(main)

    assert math.isclose(abs(ket[0]), 1, abs_tol=1e-6)
    assert ket[3] == ket[1] == ket[2] == 0


def test_feed_forward():
    @squin.kernel
    def main():
        q = squin.qubit.new(3)
        squin.h(q[0])
        squin.h(q[1])

        squin.cx(q[0], q[2])
        squin.cx(q[1], q[2])

        squin.qubit.measure(q[2])

    sim = StackMemorySimulator(min_qubits=3)

    ket = sim.state_vector(main)

    print(ket)

    zero_count = 0
    half_count = 0

    for k in ket:
        k_abs2 = abs(k) ** 2
        zero_count += k_abs2 == 0
        half_count += math.isclose(k_abs2, 0.5, abs_tol=1e-4)

    assert zero_count == 6
    assert half_count == 2
