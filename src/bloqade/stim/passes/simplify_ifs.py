from dataclasses import dataclass

from kirin import ir
from kirin.passes import Pass
from kirin.rewrite import (
    Walk,
    Chain,
    Fixpoint,
    ConstantFold,
    CommonSubexpressionElimination,
)

from ..rewrite.ifs_to_stim import StimLiftThenBody, StimSplitIfStmts


@dataclass
class StimSimplifyIfs(Pass):

    def unsafe_run(self, mt: ir.Method):

        result = Chain(
            Fixpoint(Walk(StimLiftThenBody())),
            Walk(StimSplitIfStmts()),
        ).rewrite(mt.code)

        result = (
            Fixpoint(Walk(Chain(ConstantFold(), CommonSubexpressionElimination())))
            .rewrite(mt.code)
            .join(result)
        )

        return result
