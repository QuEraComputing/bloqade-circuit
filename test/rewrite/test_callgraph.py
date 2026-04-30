from kirin import rewrite
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.analysis.callgraph import CallGraph

from bloqade import squin
from bloqade.squin.gate import stmts as squin_gate_stmts
from bloqade.rewrite.passes import CallGraphPass
from bloqade.native.dialects import gate as native_gate


class TouchHRule(RewriteRule):
    def rewrite_Statement(self, node) -> RewriteResult:
        if isinstance(node, squin_gate_stmts.H):
            return RewriteResult(has_done_something=True)
        return RewriteResult()


def test_callgraph_pass_propagates_dialects_to_callees():
    @squin.kernel
    def callee():
        q = squin.qalloc(1)
        squin.h(q[0])

    @squin.kernel
    def caller():
        callee()

    assert native_gate not in callee.dialects
    extended_dialects = caller.dialects.union([native_gate])

    CallGraphPass(extended_dialects, rewrite.Walk(TouchHRule()))(caller)

    cg = CallGraph(caller)
    new_callees = [m for m in cg.edges.keys() if m is not caller]
    assert new_callees, "expected at least one callee in the callgraph"
    for ker in new_callees:
        assert native_gate in ker.dialects
