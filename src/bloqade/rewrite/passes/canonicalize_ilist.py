from dataclasses import field, dataclass

from kirin import ir, passes
from kirin.rewrite import (
    Walk,
    Chain,
    Fixpoint,
)
from kirin.dialects.ilist import rewrite


@dataclass
class CanonicalizeIList(passes.Pass):

    fold_pass: passes.Fold = field(init=False)

    def __post_init__(self):
        self.fold_pass = passes.Fold(self.dialects, no_raise=self.no_raise)

    def unsafe_run(self, mt: ir.Method):
        result = Fixpoint(
            Walk(
                Chain(
                    rewrite.InlineGetItem(),
                    rewrite.FlattenAdd(),
                    rewrite.HintLen(),
                )
            )
        ).rewrite(mt.code)

        result = self.fold_pass(mt).join(result)
        return result
