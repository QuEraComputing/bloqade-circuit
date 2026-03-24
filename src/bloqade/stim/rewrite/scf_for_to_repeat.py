from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.dialects.scf.stmts import For, Yield

from bloqade.record_idx_helper import GetRecIdxFromPredicate, GetRecIdxFromMeasurement
from bloqade.stim.dialects.stim_cf.stmts import Repeat
from bloqade.stim.passes.repeat_eligible import get_repeat_range
from bloqade.stim.dialects.auxiliary.stmts.const import ConstInt


def _has_unresolved_record_idx_uses(result: ir.SSAValue) -> bool:
    """Check if an SSA value has transitive uses by unresolved GetRecIdx helpers."""
    visited = set()
    worklist = [result]
    while worklist:
        val = worklist.pop()
        if id(val) in visited:
            continue
        visited.add(id(val))
        for use in val.uses:
            stmt = use.stmt
            if isinstance(stmt, (GetRecIdxFromMeasurement, GetRecIdxFromPredicate)):
                return True
            # Follow through GetItem, ilist.New, etc.
            for r in stmt.results:
                worklist.append(r)
    return False


class ScfForToRepeat(RewriteRule):
    """Rewrite scf.For to stim_cf.Repeat for REPEAT-eligible loops.

    Eligibility:
    - Loop variable (first block arg) is unused
    - Iterable is a const range(N)
    - No scf.For results have unresolved GetRecIdx uses (post-loop code
      must not depend on loop-carried measurement state)

    This should run as the last rewrite step, after all squin-to-stim
    conversions and cleanup. By this point the body is fully in stim
    dialect and block args are only artifacts of the scf.For structure.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, For):
            return RewriteResult()

        repeat_range = get_repeat_range(node)
        if repeat_range is None:
            return RewriteResult()

        # Check that no scf.For results have unresolved record index uses.
        # If post-loop code references loop-carried measurement results
        # that weren't resolved by the analysis, we can't use REPEAT.
        for result in node.results:
            if _has_unresolved_record_idx_uses(result):
                return RewriteResult()

        count = len(repeat_range)

        # Replace scf.For results with corresponding initializers.
        for result, init in zip(node.results, node.initializers):
            result.replace_by(init)

        # Create count constant
        count_stmt = ConstInt(value=count)
        count_stmt.insert_before(node)

        # Create Repeat statement
        repeat = Repeat(count=count_stmt.result)
        repeat.insert_before(node)

        # Move body statements from scf.For body into Repeat body.
        # Skip the Yield terminator (not needed in REPEAT).
        repeat_block = repeat.body.blocks[0]
        body_block = node.body.blocks[0]

        stmt = body_block.first_stmt
        while stmt is not None:
            next_stmt = stmt.next_stmt
            if isinstance(stmt, Yield):
                stmt.delete()
            else:
                stmt.detach()
                repeat_block.stmts.append(stmt)
            stmt = next_stmt

        node.delete()

        return RewriteResult(has_done_something=True)
