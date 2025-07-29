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
from kirin.dialects.ilist.passes import ConstList2IList

from ..rewrite.ifs_to_stim import StimLiftThenBody, StimSplitIfStmts


@dataclass
class StimSimplifyIfs(Pass):

    def unsafe_run(self, mt: ir.Method):

        result = Chain(
            Fixpoint(Walk(StimLiftThenBody())),
            Walk(StimSplitIfStmts()),
        ).rewrite(mt.code)

        # because nested python lists don't have their
        # member lists converted to ILists, ConstantFold
        # can add python lists that can't be hashed, causing
        # issues with CSE. ConstList2IList remedies that problem here.
        result = (
            Chain(
                Fixpoint(Walk(ConstantFold())),
                Walk(ConstList2IList()),
                Walk(CommonSubexpressionElimination()),
            )
            .rewrite(mt.code)
            .join(result)
        )

        return result
