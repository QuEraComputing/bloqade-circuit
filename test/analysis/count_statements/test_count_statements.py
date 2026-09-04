from kirin import ir
from kirin.dialects import ilist

from bloqade import squin
from bloqade.qubit.stmts import New as Qalloc
from bloqade.analysis.count_statements import CountStatementAnalysis


def _count(kernel, predicate, n=1):
    counter = CountStatementAnalysis(kernel.dialects, predicate, N=n)
    counter.run(kernel)
    return counter.counts


def _count_types(*stmt_types, increment=1):
    index = {typ: i for i, typ in enumerate(stmt_types)}

    def predicate(stmt: ir.Statement) -> tuple[bool, int, int]:
        idx = index.get(type(stmt))
        if idx is None:
            return False, 0, 0
        return True, idx, increment

    return predicate


def test_broadcast_x_counts_the_gate_once():
    """A broadcast over many qubits is still one X statement in the callee."""

    @squin.kernel
    def main():
        q = squin.qalloc(4)
        squin.broadcast.x(q)

    assert _count(main, _count_types(squin.gate.stmts.X)) == [1]


def test_two_call_sites_count_separately():
    """Each invoke is entered, so two X applications count twice."""

    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.x(q[0])
        squin.x(q[0])

    assert _count(main, _count_types(squin.gate.stmts.X)) == [2]


def test_if_else_walks_both_branches():
    @squin.kernel
    def main(flag: bool):
        q = squin.qalloc(1)
        if flag:
            squin.x(q[0])
        else:
            squin.y(q[0])

    assert _count(main, _count_types(squin.gate.stmts.X, squin.gate.stmts.Y), n=2) == [
        1,
        1,
    ]


def test_if_without_else_walks_then_branch():
    @squin.kernel
    def main(flag: bool):
        q = squin.qalloc(1)
        if flag:
            squin.x(q[0])

    assert _count(main, _count_types(squin.gate.stmts.X)) == [1]


def test_for_loop_walks_body_once():
    """Trip count must not multiply the body. range(5) still has one X."""

    @squin.kernel
    def main():
        q = squin.qalloc(1)
        for _ in range(5):
            squin.x(q[0])

    assert _count(main, _count_types(squin.gate.stmts.X)) == [1]


def test_nested_kernel_is_entered():
    @squin.kernel
    def apply_xh(qubit):
        squin.x(qubit)
        squin.h(qubit)

    @squin.kernel
    def main():
        q = squin.qalloc(1)
        apply_xh(q[0])

    assert _count(main, _count_types(squin.gate.stmts.X, squin.gate.stmts.H), n=2) == [
        1,
        1,
    ]


def test_uncalled_nested_kernel_is_not_counted():
    @squin.kernel
    def unused(qubit):
        squin.x(qubit)

    @squin.kernel
    def main():
        q = squin.qalloc(1)
        return q

    assert _count(main, _count_types(squin.gate.stmts.X)) == [0]


def test_ilist_map_enters_the_mapped_function():
    @squin.kernel
    def apply_x(qubit):
        squin.x(qubit)

    @squin.kernel
    def main():
        qs = squin.qalloc(3)
        return ilist.map(apply_x, qs)

    assert _count(main, _count_types(squin.gate.stmts.X)) == [1]


def test_deep_call_chain():
    @squin.kernel
    def inner(qubit):
        squin.y(qubit)

    @squin.kernel
    def middle(qubit):
        inner(qubit)

    @squin.kernel
    def main():
        q = squin.qalloc(1)
        middle(q[0])

    assert _count(main, _count_types(squin.gate.stmts.Y)) == [1]


def test_predicate_increment():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.x(q[0])

    assert _count(main, _count_types(squin.gate.stmts.X, increment=3)) == [3]


def test_qalloc_and_gate_are_separate_buckets():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.x(q)
        squin.broadcast.h(q)

    assert _count(
        main, _count_types(Qalloc, squin.gate.stmts.X, squin.gate.stmts.H), n=3
    ) == [1, 1, 1]


def test_rerun_resets_counts():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.x(q[0])

    counter = CountStatementAnalysis(
        main.dialects, _count_types(squin.gate.stmts.X), N=1
    )
    counter.run(main)
    counter.run(main)
    assert counter.counts == [1]
