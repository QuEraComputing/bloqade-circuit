from kirin.dialects import ilist

from bloqade import squin
from bloqade.pyqrack import PyQrackQubit, StackMemorySimulator


def test_swap_exchanges_states():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.x(q[0])
        squin.swap(q[0], q[1])
        return squin.broadcast.measure(q)

    main.print()
    sim = StackMemorySimulator(min_qubits=2)
    result = sim.run(main)
    assert result.data == [0, 1]


def test_swap_is_involutive():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.x(q[0])
        squin.swap(q[0], q[1])
        squin.swap(q[0], q[1])
        return squin.broadcast.measure(q)

    sim = StackMemorySimulator(min_qubits=2)
    result = sim.run(main)
    assert result.data == [1, 0]


def test_swap_broadcast_pairwise():
    @squin.kernel
    def main():
        a = squin.qalloc(2)
        b = squin.qalloc(2)
        squin.x(a[0])
        squin.x(a[1])
        squin.broadcast.swap(a, b)
        return squin.broadcast.measure(ilist.IList([a[0], a[1], b[0], b[1]]))

    sim = StackMemorySimulator(min_qubits=4)
    result = sim.run(main)
    assert result.data == [0, 0, 1, 1]


def test_swap_with_lost_qubit_is_noop():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.x(q[0])
        squin.qubit_loss(1.0, q[1])
        squin.swap(q[0], q[1])
        return q[0]

    sim = StackMemorySimulator(min_qubits=2)
    qubit = sim.run(main)
    assert isinstance(qubit, PyQrackQubit)
    assert qubit.is_active()
