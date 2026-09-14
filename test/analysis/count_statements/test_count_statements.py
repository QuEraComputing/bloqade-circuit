from collections import Counter

from kirin import ir
from kirin.dialects import ilist

from bloqade import squin
from bloqade.qubit.stmts import New as Qalloc
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.analysis.count_statements import CountStatementAnalysis


def _count(kernel, predicate):
    analysis = CountStatementAnalysis(kernel.dialects, predicate)
    analysis.run(kernel)
    return analysis.counter


def _count_types(*stmt_types, increment=1):
    types = set(stmt_types)

    def predicate(stmt: ir.Statement) -> tuple[bool, int]:
        if type(stmt) not in types:
            return False, 0
        return True, increment

    return predicate


def test_broadcast_x_counts_the_gate_once():
    """A broadcast over many qubits is still one X statement in the callee."""

    @squin.kernel
    def main():
        q = squin.qalloc(4)
        squin.broadcast.x(q)

    assert _count(main, _count_types(squin.gate.stmts.X)) == Counter(
        {squin.gate.stmts.X: 1}
    )


def test_two_call_sites_count_separately():
    """Each invoke is entered, so two X applications count twice."""

    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.x(q[0])
        squin.x(q[0])

    counter = _count(main, _count_types(squin.gate.stmts.X))
    assert len(counter) == 1
    assert counter == Counter({squin.gate.stmts.X: 2})


def test_if_else_walks_both_branches():
    @squin.kernel
    def main(flag: bool):
        q = squin.qalloc(1)
        if flag:
            squin.x(q[0])
        else:
            squin.y(q[0])

    counter = _count(main, _count_types(squin.gate.stmts.X, squin.gate.stmts.Y))
    assert counter == Counter({squin.gate.stmts.X: 1, squin.gate.stmts.Y: 1})


def test_if_without_else_walks_then_branch():
    @squin.kernel
    def main(flag: bool):
        q = squin.qalloc(1)
        if flag:
            squin.x(q[0])

    counter = _count(main, _count_types(squin.gate.stmts.X))
    assert counter == Counter({squin.gate.stmts.X: 1})


def test_for_loop_walks_body_once():
    """Trip count must not multiply the body. range(5) still has one X."""

    @squin.kernel
    def main():
        q = squin.qalloc(1)
        for _ in range(5):
            squin.x(q[0])

    counter = _count(main, _count_types(squin.gate.stmts.X))
    assert counter == Counter({squin.gate.stmts.X: 1})


def test_nested_kernel_is_entered():
    @squin.kernel
    def apply_xh(qubit):
        squin.x(qubit)
        squin.h(qubit)

    @squin.kernel
    def main():
        q = squin.qalloc(1)
        apply_xh(q[0])

    counter = _count(main, _count_types(squin.gate.stmts.X, squin.gate.stmts.H))
    assert counter == Counter({squin.gate.stmts.X: 1, squin.gate.stmts.H: 1})


def test_uncalled_nested_kernel_is_not_counted():
    @squin.kernel
    def unused(qubit):
        squin.x(qubit)

    @squin.kernel
    def main():
        q = squin.qalloc(1)
        return q

    assert _count(main, _count_types(squin.gate.stmts.X)) == Counter()


def test_ilist_map_enters_the_mapped_function():
    @squin.kernel
    def apply_x(qubit):
        squin.x(qubit)

    @squin.kernel
    def main():
        qs = squin.qalloc(3)
        return ilist.map(apply_x, qs)

    counter = _count(main, _count_types(squin.gate.stmts.X))
    assert counter == Counter({squin.gate.stmts.X: 1})


def test_ilist_foldl_enters_the_fold_function_once():
    @squin.kernel
    def apply_x(acc, qubit):
        squin.x(qubit)
        return acc

    @squin.kernel
    def main():
        qs = squin.qalloc(3)
        return ilist.foldl(apply_x, qs, 0)

    counter = _count(main, _count_types(squin.gate.stmts.X))
    assert counter == Counter({squin.gate.stmts.X: 1})


def test_ilist_scan_enters_the_scan_function_once():
    @squin.kernel
    def apply_x(acc, qubit):
        squin.x(qubit)
        return acc, qubit

    @squin.kernel
    def main():
        qs = squin.qalloc(3)
        return ilist.scan(apply_x, qs, 0)

    counter = _count(main, _count_types(squin.gate.stmts.X))
    assert counter == Counter({squin.gate.stmts.X: 1})


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

    counter = _count(main, _count_types(squin.gate.stmts.Y))
    assert counter == Counter({squin.gate.stmts.Y: 1})


def test_predicate_increment():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.x(q[0])

    counter = _count(main, _count_types(squin.gate.stmts.X, increment=3))
    assert len(counter) == 1
    assert counter == Counter({squin.gate.stmts.X: 3})


def test_qalloc_and_gate_are_separate_buckets():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.x(q)
        squin.broadcast.h(q)

    counter = _count(main, _count_types(Qalloc, squin.gate.stmts.X, squin.gate.stmts.H))
    assert counter == Counter({Qalloc: 1, squin.gate.stmts.X: 1, squin.gate.stmts.H: 1})


def test_rerun_resets_counts():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.x(q[0])

    analysis = CountStatementAnalysis(main.dialects, _count_types(squin.gate.stmts.X))
    analysis.run(main)
    analysis.run(main)
    assert analysis.counter == Counter({squin.gate.stmts.X: 1})


def test_unroll_agrees_with_structured():

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.x(q[0])
        squin.broadcast.x(q)

    analysis = CountStatementAnalysis(main.dialects, _count_types(squin.gate.stmts.X))
    analysis.run(main)

    counter1 = analysis.counter.copy()

    AggressiveUnroll(main.dialects).fixpoint(main)

    analysis.run(main)
    counter2 = analysis.counter.copy()

    assert counter1 == counter2
    assert counter1[squin.gate.stmts.X] == 2
