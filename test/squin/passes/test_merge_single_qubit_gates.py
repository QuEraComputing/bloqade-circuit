from kirin import ir

from bloqade import squin as sq
from bloqade.squin import gate
from bloqade.squin.passes import MergeSingleQubitGatesPass


def filter_statements_by_type(
    method: ir.Method, types: tuple[type, ...]
) -> list[ir.Statement]:
    return [
        stmt
        for stmt in method.callable_region.blocks[0].stmts
        if isinstance(stmt, types)
    ]


def test_merge_three_t_gates_to_single_u3():

    @sq.kernel
    def main():
        q = sq.qalloc(1)
        sq.t(q[0])
        sq.t(q[0])
        sq.t(q[0])
        return

    MergeSingleQubitGatesPass(dialects=main.dialects).unsafe_run(main)

    t_stmts = filter_statements_by_type(main, (gate.stmts.T,))
    u3_stmts = filter_statements_by_type(main, (gate.stmts.U3,))

    assert len(t_stmts) == 0
    assert len(u3_stmts) == 1
