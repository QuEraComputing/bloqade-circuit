from dataclasses import dataclass

from kirin import ir
from kirin.passes import Pass
from kirin.rewrite import (
    Walk,
    Chain,
    Fixpoint,
)
from kirin.analysis import const

from ..rules.flatten_ilist import FlattenAddOpIList
from ..rules.inline_getitem_ilist import InlineGetItemFromIList


@dataclass
class CanonicalizeIList(Pass):

    def unsafe_run(self, mt: ir.Method):

        cp_result_frame, _ = const.Propagate(dialects=mt.dialects).run_analysis(mt)

        return Fixpoint(
            Chain(
                Walk(InlineGetItemFromIList(constprop_result=cp_result_frame.entries)),
                Walk(FlattenAddOpIList()),
            )
        ).rewrite(mt.code)
