from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult

import bloqade.qasm2.dialects.uop.stmts as uop_stmts


class QASM2IdToSquin(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        if not isinstance(node, uop_stmts.Id):
            return RewriteResult()

        node.delete()
        return RewriteResult(has_done_something=True)
