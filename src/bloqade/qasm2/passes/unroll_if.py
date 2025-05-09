from kirin import ir
from kirin.passes import Pass
from kirin.rewrite import (
    Walk,
    Chain,
    Fixpoint,
    ConstantFold,
    CommonSubexpressionElimination,
)

from ..rewrite.split_ifs import LiftThenBody, SplitIfStmts


class UnrollIfs(Pass):
    """This pass lifts statements that are not UOP out of the if body and then splits whatever is left into multiple if statements so you obtain valid QASM2"""

    def unsafe_run(self, mt: ir.Method):
        result = Walk(LiftThenBody()).rewrite(mt.code)
        result = Walk(SplitIfStmts()).rewrite(mt.code).join(result)
        result = (
            Fixpoint(Walk(Chain(ConstantFold(), CommonSubexpressionElimination())))
            .rewrite(mt.code)
            .join(result)
        )
        return result
