"""Remove leftover non-stim dialect statements after conversion.

After the full squin-to-stim conversion pipeline, some statements from
non-stim dialects may survive (qubit.New, qubit.Measure, py.ilist ops, etc.)
because DCE doesn't touch impure ops. This pass removes statements from
an explicit delete-list when all their results have no uses, and warns
if an unexpected non-stim statement survives.
"""

import warnings

from kirin import ir
from kirin.dialects import py, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.qubit import stmts as qubit_stmts

# Statements expected to be left over after squin-to-stim conversion.
# These are inputs to rewrite rules whose results become dead once the
# stim replacements take over.
EXPECTED_DEAD: tuple[type[ir.Statement], ...] = (
    qubit_stmts.New,
    qubit_stmts.Measure,
    py.constant.Constant,
    ilist.stmts.New,
    py.binop.Add,
)


class RemoveDeadNonStimStatements(RewriteRule):
    """Remove dead statements from an explicit delete-list.

    Statements not in the delete-list that survive from non-stim dialects
    trigger a warning, making it easier to catch missed rewrites.
    """

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

        if isinstance(node, EXPECTED_DEAD):
            node.delete()
            return RewriteResult(has_done_something=True)

        warnings.warn(
            f"Unexpected non-stim statement survived conversion: "
            f"{type(node).__name__} from {node.dialect}",
        )
        return RewriteResult()
