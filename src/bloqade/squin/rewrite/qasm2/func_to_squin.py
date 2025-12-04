from kirin import ir
from kirin.dialects import func
from kirin.rewrite.abc import RewriteRule, RewriteResult


class QASM2FuncToSquin(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        if not isinstance(node, func.Invoke):
            return RewriteResult()

        callee = node.callee

        return self.rewrite_Region(callee.callable_region)

    def rewrite_Region(self, region: ir.Region) -> RewriteResult:

        rewrite_result = RewriteResult()

        for stmt in list(region.walk()):
            result = self.rewrite_Statement(stmt)
            rewrite_result = rewrite_result.join(result)

        return rewrite_result
