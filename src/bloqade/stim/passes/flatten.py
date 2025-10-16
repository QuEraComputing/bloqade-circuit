# Taken from Phillip Weinberg's bloqade-shuttle implementation
from dataclasses import field, dataclass

from kirin import ir
from kirin.passes import Pass, HintConst
from kirin.rewrite import (
    Walk,
    Chain,
    Fixpoint,
    Call2Invoke,
    ConstantFold,
    InlineGetItem,
    InlineGetField,
    DeadCodeElimination,
)
from kirin.dialects import ilist
from kirin.ir.method import Method
from kirin.rewrite.abc import RewriteResult
from kirin.rewrite.cse import CommonSubexpressionElimination
from kirin.passes.inline import InlinePass

from bloqade.qasm2.passes.fold import AggressiveUnroll
from bloqade.stim.passes.simplify_ifs import StimSimplifyIfs


@dataclass
class Fold(Pass):
    hint_const: HintConst = field(init=False)

    def __post_init__(self):
        self.hint_const = HintConst(self.dialects, no_raise=self.no_raise)

    def unsafe_run(self, mt: Method) -> RewriteResult:
        result = RewriteResult()
        result = self.hint_const.unsafe_run(mt).join(result)
        rule = Chain(
            ConstantFold(),
            Call2Invoke(),
            InlineGetField(),
            InlineGetItem(),
            ilist.rewrite.InlineGetItem(),
            ilist.rewrite.HintLen(),
            DeadCodeElimination(),
            CommonSubexpressionElimination(),
        )
        result = Fixpoint(Walk(rule)).rewrite(mt.code).join(result)

        return result


class Flatten(Pass):
    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        rewrite_result = InlinePass(dialects=mt.dialects, no_raise=self.no_raise)(mt)
        rewrite_result = AggressiveUnroll(dialects=mt.dialects, no_raise=self.no_raise)(
            mt
        ).join(rewrite_result)
        rewrite_result = StimSimplifyIfs(dialects=mt.dialects, no_raise=self.no_raise)(
            mt
        ).join(rewrite_result)

        return rewrite_result
