from kirin import ir
from kirin.passes import Pass
from kirin.rewrite import (
    Walk,
    Chain,
    Fixpoint,
    ConstantFold,
    CommonSubexpressionElimination,
)
from kirin.passes.hint_const import HintConst

from bloqade.qasm2.rewrite.insert_qubits import InsertGetQubit


class LiftQubits(Pass):
    """This pass lifts the creation of qubits to the block where the register is defined."""

    def unsafe_run(self, mt: ir.Method):
        result = Walk(InsertGetQubit()).rewrite(mt.code)
        result = HintConst(self.dialects).unsafe_run(mt).join(result)
        result = (
            Fixpoint(Walk(Chain(ConstantFold(), CommonSubexpressionElimination())))
            .rewrite(mt.code)
            .join(result)
        )
        return result
