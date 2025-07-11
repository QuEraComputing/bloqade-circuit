from dataclasses import field, dataclass

from kirin import ir
from kirin.dialects import scf, func
from kirin.rewrite.abc import RewriteRule, RewriteResult


@dataclass
class LiftThenBody(RewriteRule):
    """
    Lifts anything that's not in the `exclude_stmts` in the *then* body


    Args:
        exclude_stmts: A tuple of statement types that should not be lifted from the then body.
            Defaults to an empty tuple, meaning all statements are lifted.

    """

    exclude_stmts: tuple[type[ir.Statement], ...] = field(default_factory=tuple)

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, scf.IfElse):
            return RewriteResult()

        then_stmts = node.then_body.stmts()

        lift_stmts = [
            stmt for stmt in then_stmts if not isinstance(stmt, self.exclude_stmts)
        ]

        if len(lift_stmts) == 0:
            return RewriteResult()

        for stmt in lift_stmts:
            stmt.detach()
            stmt.insert_before(node)

        return RewriteResult(has_done_something=True)


class SplitIfStmts(RewriteRule):
    """Splits the then body of an if-else statement into multiple if statements"""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, scf.IfElse):
            return RewriteResult()

        *stmts, yield_or_return = node.then_body.stmts()

        if len(stmts) == 1:
            return RewriteResult()

        is_yield = isinstance(yield_or_return, scf.Yield)

        for stmt in stmts:
            stmt.detach()

            yield_or_return = scf.Yield() if is_yield else func.Return()

            then_block = ir.Block((stmt, yield_or_return), argtypes=(node.cond.type,))
            then_body = ir.Region(then_block)
            else_body = node.else_body.clone()
            else_body.detach()
            new_if = scf.IfElse(
                cond=node.cond, then_body=then_body, else_body=else_body
            )

            new_if.insert_before(node)

        node.delete()

        return RewriteResult(has_done_something=True)
