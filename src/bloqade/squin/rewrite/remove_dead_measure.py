from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import qubit


class RemoveDeadMeasure(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        if not isinstance(node, qubit.stmts.Measure):
            return RewriteResult()

        if bool(node.result.uses):
            return RewriteResult()
        else:
            node.delete()

        return RewriteResult(has_done_something=True)
