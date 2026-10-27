import cirq
from kirin.dialects import ilist

from bloqade import squin
from bloqade.cirq_utils import emit_circuit


def test_broadcast_cz_stays_in_one_moment():
    @squin.kernel
    def main():
        q = squin.qalloc(4)
        squin.h(q[0])
        squin.broadcast.cz(ilist.IList([q[0], q[2]]), ilist.IList([q[1], q[3]]))

    circuit = emit_circuit(main)
    q = cirq.LineQubit.range(4)

    assert circuit == cirq.Circuit(
        cirq.Moment([cirq.H(q[0])]),
        cirq.Moment([cirq.CZ(q[0], q[1]), cirq.CZ(q[2], q[3])]),
    )


def test_broadcast_uses_earliest_common_moment():
    @squin.kernel
    def main():
        q = squin.qalloc(5)
        squin.h(q[0])
        squin.cx(q[4], q[2])
        squin.h(q[2])
        squin.h(q[4])
        squin.h(q[4])
        squin.broadcast.cz(ilist.IList([q[0], q[2]]), ilist.IList([q[1], q[3]]))

    circuit = emit_circuit(main)
    q = cirq.LineQubit.range(5)

    assert circuit == cirq.Circuit(
        cirq.Moment([cirq.H(q[0]), cirq.CNOT(q[4], q[2])]),
        cirq.Moment([cirq.H(q[2]), cirq.H(q[4])]),
        cirq.Moment([cirq.H(q[4]), cirq.CZ(q[0], q[1]), cirq.CZ(q[2], q[3])]),
    )


def test_broadcast_single_qubit_gates_stay_in_one_moment():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        squin.h(q[0])
        squin.broadcast.x(ilist.IList([q[0], q[1], q[2]]))

    circuit = emit_circuit(main)
    q = cirq.LineQubit.range(3)

    assert circuit == cirq.Circuit(
        cirq.Moment([cirq.H(q[0])]),
        cirq.Moment([cirq.X(q[0]), cirq.X(q[1]), cirq.X(q[2])]),
    )
