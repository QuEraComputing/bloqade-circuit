from kirin import ir
from kirin.passes import Pass
from kirin.rewrite import (
    Walk,
    Chain,
    Fixpoint,
    ConstantFold,
    CommonSubexpressionElimination,
)
from kirin.dialects import scf, func

from bloqade.rewrite.rules import LiftThenBody, SplitIfStmts

from ..dialects.uop.stmts import SingleQubitGate, TwoQubitCtrlGate
from ..dialects.core.stmts import Reset, Measure

AllowedThenType = (SingleQubitGate, TwoQubitCtrlGate, Measure, Reset)
DontLiftType = AllowedThenType + (scf.Yield, func.Return, func.Invoke)


class UnrollIfs(Pass):
    """This pass lifts statements that are not UOP out of the if body and then splits whatever is left into multiple if statements so you obtain valid QASM2"""

    def unsafe_run(self, mt: ir.Method):
        result = Walk(LiftThenBody(exclude_stmts=DontLiftType)).rewrite(mt.code)
        result = Walk(SplitIfStmts()).rewrite(mt.code).join(result)
        result = (
            Fixpoint(Walk(Chain(ConstantFold(), CommonSubexpressionElimination())))
            .rewrite(mt.code)
            .join(result)
        )
        return result
