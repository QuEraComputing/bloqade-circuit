import math

import numpy as np
import pytest
from kirin.dialects import ilist

from bloqade import squin
from bloqade.qrb import QRB, QRBQubit, StackMemorySimulator


def test_qubit():
    @squin.kernel
    def new():
        return squin.qalloc(3)

    new.print()

    target = QRB(
        3, qrb_options={"isBinaryDecisionTree": False, "isStabilizerHybrid": True}
    )
    result = target.run(new)
    assert isinstance(result, ilist.IList)
    assert isinstance(qubit := result[0], QRBQubit)

    # qrackbind: state_vector is a property returning np.ndarray
    out = np.array(qubit.sim_reg.state_vector)

    i = np.abs(out).argmax()
    out /= out[i] / np.abs(out[i])

    expected = np.zeros_like(out)
    expected[0] = 1.0

    assert np.allclose(out, expected, atol=2.2e-7)

    @squin.kernel
    def m():
        q = squin.qalloc(3)
        m = squin.broadcast.measure(q)
        return m

    target = QRB(3)
    result = target.run(m)
    assert isinstance(result, ilist.IList)
    assert result.data == [0, 0, 0]


def test_x():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.x(q[0])
        return squin.qubit.measure(q[0])

    target = QRB(1)
    result = target.run(main)
    assert result == 1


@pytest.mark.parametrize(
    "op_name",
    ["x", "y", "z", "h", "s", "t", "sqrt_x", "sqrt_y", "sqrt_z"],
)
def test_basic_ops(op_name: str):
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        getattr(squin, op_name)(q[0])
        return q

    target = QRB(1)
    result = target.run(main)
    assert isinstance(result, ilist.IList)
    assert isinstance(qubit := result[0], QRBQubit)

    # qrackbind: state_vector property
    ket = qubit.sim_reg.state_vector
    n = sum([abs(k) ** 2 for k in ket])
    assert math.isclose(n, 1, abs_tol=1e-6)


def test_cx():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.cx(q[0], q[1])
        return squin.qubit.measure(q[1])

    target = QRB(2)
    result = target.run(main)
    assert result == 0

    @squin.kernel
    def main2():
        q = squin.qalloc(2)
        squin.x(q[0])
        squin.cx(q[0], q[1])
        return squin.qubit.measure(q[0])

    target = QRB(2)
    result = target.run(main2)
    assert result == 1


def test_rot():
    @squin.kernel
    def main_x():
        q = squin.qalloc(1)
        squin.rx(math.pi, q[0])
        return squin.qubit.measure(q[0])

    target = QRB(1)
    assert target.run(main_x) == 1

    @squin.kernel
    def main_y():
        q = squin.qalloc(1)
        squin.ry(math.pi, q[0])
        return squin.qubit.measure(q[0])

    target = QRB(1)
    assert target.run(main_y) == 1

    @squin.kernel
    def main_z():
        q = squin.qalloc(1)
        squin.rz(math.pi, q[0])
        return squin.qubit.measure(q[0])

    target = QRB(1)
    assert target.run(main_z) == 0


def test_u3():
    @squin.kernel
    def broadcast_h():
        q = squin.qalloc(3)
        squin.broadcast.u3(math.pi / 2.0, 0, 0, q)
        return q

    target = QRB(3)
    q = target.run(broadcast_h)

    assert isinstance(q, ilist.IList)
    assert isinstance(qubit := q[0], QRBQubit)

    out = np.array(qubit.sim_reg.state_vector)
    phase = out[0] / abs(out[0])
    out = out / phase

    for element in out:
        assert math.isclose(element.real, 1 / math.sqrt(8), abs_tol=2.2e-7)
        assert math.isclose(element.imag, 0, abs_tol=2.2e-7)


def test_reset():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.h(q)
        squin.broadcast.reset(q)

    sim = StackMemorySimulator(min_qubits=2)
    ket = sim.state_vector(main)

    assert math.isclose(abs(ket[0]), 1, abs_tol=1e-6)
    assert ket[3] == ket[1] == ket[2] == 0
