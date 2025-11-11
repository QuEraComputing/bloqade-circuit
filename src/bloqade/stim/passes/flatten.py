# Taken from Phillip Weinberg's bloqade-shuttle implementation
from dataclasses import field, dataclass

from kirin import ir
from kirin.passes import Pass
from kirin.rewrite.abc import RewriteResult

from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.stim.passes.simplify_ifs import StimSimplifyIfs


@dataclass
class Flatten(Pass):

    unroll: AggressiveUnroll = field(init=False)
    simplify_if: StimSimplifyIfs = field(init=False)

    def __post_init__(self):
        self.unroll = AggressiveUnroll(self.dialects, no_raise=self.no_raise)
        self.simplify_if = StimSimplifyIfs(self.dialects, no_raise=self.no_raise)

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        rewrite_result = RewriteResult()
        rewrite_result = self.simplify_if(mt).join(rewrite_result)
        rewrite_result = self.unroll(mt).join(rewrite_result)
        return rewrite_result
