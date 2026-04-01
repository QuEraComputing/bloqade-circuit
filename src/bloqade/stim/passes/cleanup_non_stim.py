"""Remove leftover non-stim dialect statements after conversion.

After the full squin-to-stim conversion pipeline, some statements from
non-stim dialects may survive because DCE doesn't touch impure ops.
This pass explicitly deletes known impure leftovers (qubit.New,
qubit.Measure), applies DCE logic for any dead pure statement (to
handle cascading orphans), and warns if an unexpected impure non-stim
statement survives.
"""

import warnings

from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.qubit import stmts as qubit_stmts

# Impure statements expected to be left over after squin-to-stim conversion.
# DCE can't remove these because they have side effects.
EXPECTED_IMPURE_DEAD: tuple[type[ir.Statement], ...] = (
    qubit_stmts.New,
    qubit_stmts.Measure,
)


class RemoveDeadNonStimStatements(RewriteRule):
    """Remove dead non-stim statements after conversion.

    - Known impure leftovers (EXPECTED_IMPURE_DEAD): deleted when unused.
    - Pure non-stim statements with no uses: deleted (handles cascading
      orphans from impure deletions, e.g. py.Constant feeding a qubit count).
    - Unexpected impure non-stim survivors: warned about.
    """

    def __init__(self, keep: ir.DialectGroup):
        self.keep = keep

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if node.dialect is None or node.dialect in self.keep:
            return RewriteResult()

        if node.regions or node.has_trait(ir.IsTerminator):
            return RewriteResult()

        if any(len(r.uses) > 0 for r in node.results):
            return RewriteResult()

        # Dead and pure — always safe to delete (same as DCE).
        if self._is_pure(node):
            node.delete()
            return RewriteResult(has_done_something=True)

        # Dead and impure — only delete if expected.
        if isinstance(node, EXPECTED_IMPURE_DEAD):
            node.delete()
            return RewriteResult(has_done_something=True)

        warnings.warn(
            f"Unexpected non-stim statement survived conversion: "
            f"{type(node).__name__} from {node.dialect}",
        )
        return RewriteResult()

    @staticmethod
    def _is_pure(node: ir.Statement) -> bool:
        if node.has_trait(ir.Pure):
            return True
        if (trait := node.get_trait(ir.MaybePure)) and trait.is_pure(node):
            return True
        return False
