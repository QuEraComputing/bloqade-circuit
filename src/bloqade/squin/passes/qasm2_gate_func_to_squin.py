from kirin import ir, passes
from kirin.rewrite import Walk, Chain
from kirin.dialects import func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.rewrite.passes import CallGraphPass
from bloqade.qasm2.passes.qasm2py import _QASM2Py as QASM2ToPyRule

from ..rewrite import qasm2 as qasm2_rule


class QASM2GateFuncToKirinFunc(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        from bloqade.qasm2.dialects.expr.stmts import GateFunction

        if not isinstance(node, GateFunction):
            return RewriteResult()

        kirin_func = func.Function(
            sym_name=node.sym_name,
            signature=node.signature,
            body=node.body,
            slots=node.slots,
        )
        node.replace_by(kirin_func)

        return RewriteResult(has_done_something=True)


class QASM2GateFuncToSquinPass(passes.Pass):

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        convert_to_kirin_func = CallGraphPass(
            dialects=mt.dialects, rule=Walk(QASM2GateFuncToKirinFunc())
        )
        rewrite_result = convert_to_kirin_func(mt)

        combined_qasm2_rules = Walk(
            Chain(
                QASM2ToPyRule(),
                qasm2_rule.QASM2CoreToSquin(),
                qasm2_rule.QASM2UOPToSquin(),
                qasm2_rule.QASM2NoiseToSquin(),
                qasm2_rule.QASM2GlobParallelToSquin(),
            )
        )

        body_conversion_pass = CallGraphPass(
            dialects=mt.dialects, rule=combined_qasm2_rules
        )
        rewrite_result = body_conversion_pass(mt).join(rewrite_result)

        return rewrite_result
