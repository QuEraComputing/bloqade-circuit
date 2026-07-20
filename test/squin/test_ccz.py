import pytest
from kirin.dialects import ilist

from bloqade import squin
from bloqade.pyqrack import PyQrackQubit, StackMemorySimulator


@pytest.mark.parametrize(
    "control1_state, control2_state, expected",
    [(0, 0, 0), (0, 1, 0), (1, 0, 0), (1, 1, 1)],
)
def test_ccz_flips_phase_only_when_both_controls_set(
    control1_state: int, control2_state: int, expected: int
):
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        if control1_state == 1:
            squin.x(q[0])
        if control2_state == 1:
            squin.x(q[1])
        squin.h(q[2])
        squin.ccz(q[0], q[1], q[2])
        squin.h(q[2])
        return squin.measure(q[2])

    sim = StackMemorySimulator(min_qubits=3)
    result = sim.run(main)
    assert result == expected


def test_ccz_is_involutive():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        squin.x(q[0])
        squin.x(q[1])
        squin.h(q[2])
        squin.ccz(q[0], q[1], q[2])
        squin.ccz(q[0], q[1], q[2])
        squin.h(q[2])
        return squin.broadcast.measure(q)

    sim = StackMemorySimulator(min_qubits=3)
    result = sim.run(main)
    assert result.data == [1, 1, 0]


def test_ccz_broadcast_triplewise():
    @squin.kernel
    def main():
        a = squin.qalloc(2)
        b = squin.qalloc(2)
        c = squin.qalloc(2)
        squin.broadcast.x(a)
        squin.x(b[0])
        squin.broadcast.h(c)
        squin.broadcast.ccz(a, b, c)
        squin.broadcast.h(c)
        return squin.broadcast.measure(ilist.IList([c[0], c[1]]))

    sim = StackMemorySimulator(min_qubits=6)
    result = sim.run(main)
    assert result.data == [1, 0]


def test_ccz_with_lost_qubit_is_noop():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        squin.x(q[0])
        squin.x(q[1])
        squin.qubit_loss(1.0, q[1])
        squin.ccz(q[0], q[1], q[2])
        return q[2]

    sim = StackMemorySimulator(min_qubits=3)
    qubit = sim.run(main)
    assert isinstance(qubit, PyQrackQubit)
    assert qubit.is_active()
