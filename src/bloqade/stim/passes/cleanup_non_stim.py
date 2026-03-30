"""Remove leftover non-stim dialect statements after conversion.

After the full squin-to-stim conversion pipeline, some statements from
non-stim dialects may survive (qubit.New, qubit.Measure, py.ilist ops, etc.)
because DCE doesn't touch impure ops. This pass removes any statement
from a non-stim dialect when all its results have no uses.
"""

from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult


class RemoveDeadNonStimStatements(RewriteRule):
    """Remove dead statements from non-stim dialects."""

    def __init__(self, keep: ir.DialectGroup):
        self.keep = keep

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if node.dialect is None or node.dialect in self.keep:
            return RewriteResult()

        # Keep statements whose results still have uses
        if any(len(r.uses) > 0 for r in node.results):
            return RewriteResult()

        # Don't remove statements with regions (like scf.For)
        if node.regions:
            return RewriteResult()

        # Don't remove terminators (Yield, Return, Branch, etc.)
        if node.has_trait(ir.IsTerminator):
            return RewriteResult()

        node.delete()
        return RewriteResult(has_done_something=True)
