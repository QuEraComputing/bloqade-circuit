from kirin import rewrite
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.analysis.callgraph import CallGraph

from bloqade import squin
from bloqade.rewrite.passes import CallGraphPass
from bloqade.native.dialects import gate as native_gate


class _AlwaysReportsChange(RewriteRule):
    # CallGraphPass only commits its callee replacements into the caller
    # when the rule reports a change. Without that commit step, a
    # CallGraph lookup on the caller after the pass still resolves to
    # the original (uncopied) callees, making any dialect check below
    # vacuous. This rule signals a change without actually mutating the IR.
    def rewrite_Statement(self, node) -> RewriteResult:
        return RewriteResult(has_done_something=True)


def test_callgraph_pass_propagates_dialects_to_callee_copies():
    # Regression: CallGraphPass must forward its dialect set to
    # `similar()` when copying callees. Otherwise callee copies keep
    # their original (narrower) dialect group and rewrites targeting
    # the extended dialects silently fail to apply inside callees.
    @squin.kernel
    def callee():
        q = squin.qalloc(1)
        return q

    @squin.kernel
    def caller():
        callee()

    assert native_gate not in callee.dialects
    extended_dialects = caller.dialects.union([native_gate])

    CallGraphPass(extended_dialects, rewrite.Walk(_AlwaysReportsChange()))(caller)

    new_callees = [m for m in CallGraph(caller).edges.keys() if m is not caller]
    assert new_callees, "expected the callee in the post-rewrite callgraph"
    for ker in new_callees:
        assert native_gate in ker.dialects, (
            "callee copies should inherit the extended dialect set "
            "passed to CallGraphPass"
        )
