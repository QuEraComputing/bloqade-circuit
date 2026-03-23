from kirin import ir, passes
from kirin.rewrite import Walk, Chain
from kirin.analysis import CallGraph
from kirin.dialects import func
from kirin.rewrite.abc import RewriteResult

from bloqade.rewrite.passes import CallGraphPass

from ..rewrite.qasm3 import (
    QASM3DirectToSquin,
    QASM3ModifiedToSquin,
)


class QASM3GateFuncToSquinPass(passes.Pass):

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        from bloqade.qasm3.dialects.expr.stmts import GateFunction

        result = RewriteResult()

        # Convert GateFunction -> func.Function on all callees.
        # GateFunction is the root `code` node of gate methods, so we
        # can't use replace_by (it has no parent).  Instead we build a
        # new func.Function and assign it to mt.code directly.
        cg = CallGraph(mt)
        all_methods = set(cg.edges.keys())
        all_methods.add(mt)

        for method in all_methods:
            if isinstance(method.code, GateFunction):
                kirin_func = func.Function(
                    sym_name=method.code.sym_name,
                    signature=method.code.signature,
                    body=method.code.body,
                    slots=method.code.slots,
                )
                method.code = kirin_func
                result = RewriteResult(has_done_something=True)

        # Now apply the QASM3 -> squin rewrite rules across the call graph
        combined_qasm3_rules = Walk(
            Chain(
                QASM3DirectToSquin(),
                QASM3ModifiedToSquin(),
            )
        )

        body_conversion_pass = CallGraphPass(
            dialects=mt.dialects, rule=combined_qasm3_rules
        )
        result = body_conversion_pass(mt).join(result)

        return result
