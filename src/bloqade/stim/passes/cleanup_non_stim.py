"""Remove leftover non-stim dialect statements after conversion.

After the full squin-to-stim conversion pipeline, some non-stim statements
survive because DCE doesn't touch impure ops. This pass removes:
- Dead pure non-stim statements (cascading orphans from other deletions).
- Dead impure statements from an explicit list of expected leftovers.
Unexpected impure survivors trigger a warning to surface missed rewrites.
"""

import warnings

from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.qubit import stmts as qubit_stmts

# Impure statements expected to be left over after squin-to-stim conversion.
# These don't have stim equivalents — their side effects are subsumed by
# the stim statements that replaced their consumers (e.g. qubit.New
# becomes irrelevant once all gates using that qubit are converted).
EXPECTED_IMPURE_DEAD: tuple[type[ir.Statement], ...] = (
    qubit_stmts.New,
    qubit_stmts.Measure,
)


class RemoveDeadNonStimStatements(RewriteRule):
    """Remove dead non-stim statements after conversion.

    - Dead pure non-stim statements: always safe to delete.
    - Dead impure statements in EXPECTED_IMPURE_DEAD: deleted.
    - Dead impure statements NOT in the list: warned about (likely a missed rewrite).
    """

    def __init__(self, keep: ir.DialectGroup):
        self.keep = keep

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, EXPECTED_IMPURE_DEAD):
            # Warn about unexpected dead impure non-stim statements.
            if (
                node.dialect is not None
                and node.dialect not in self.keep
                and not node.regions
                and not node.has_trait(ir.IsTerminator)
                and not node.has_trait(ir.Pure)
                and not (
                    (trait := node.get_trait(ir.MaybePure)) and trait.is_pure(node)
                )
                and all(len(r.uses) == 0 for r in node.results)
            ):
                warnings.warn(
                    f"Unexpected non-stim statement survived conversion: "
                    f"{type(node).__name__} from {node.dialect}",
                )
            return RewriteResult()

        if any(len(r.uses) > 0 for r in node.results):
            return RewriteResult()

        node.delete()
        return RewriteResult(has_done_something=True)
