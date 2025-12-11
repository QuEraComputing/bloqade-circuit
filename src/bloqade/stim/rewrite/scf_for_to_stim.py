from kirin import ir
from kirin.dialects import scf
from kirin.rewrite.abc import RewriteRule, RewriteResult


class ScfForToStim(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement):
        if not isinstance(node, scf.stmts.For):
            return RewriteResult()

        return RewriteResult(has_done_something=True)

    def rewrite_Region(self, node: ir.Region):
        return RewriteResult()

    def rewrite_Block(self, node: ir.Block):
        return RewriteResult()
