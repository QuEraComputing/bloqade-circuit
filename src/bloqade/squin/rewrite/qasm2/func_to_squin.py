from kirin import ir
from kirin.rewrite import Walk, Chain
from kirin.dialects import func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from .. import qasm2 as qasm2_rules


class QASM2FuncToSquin(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        rewrite_result = RewriteResult()
        if not isinstance(node, func.Invoke):
            return rewrite_result

        callee = node.callee
        region = callee.callable_region

        for stmt in region.walk():
            rewrite_result = (
                Walk(
                    Chain(
                        qasm2_rules.QASM2FuncToSquin(),
                        qasm2_rules.QASM2ExprToSquin(),
                        qasm2_rules.QASM2CoreToSquin(),
                        qasm2_rules.QASM2UOPToSquin(),
                        qasm2_rules.QASM2GlobParallelToSquin(),
                        qasm2_rules.QASM2NoiseToSquin(),
                    )
                )
                .rewrite(stmt)
                .join(rewrite_result)
            )

        return rewrite_result
