from typing import Callable
from dataclasses import field, dataclass

from kirin import ir
from kirin.passes import Pass, HintConst, TypeInfer
from kirin.rewrite import (
    Walk,
    Chain,
    Inline,
    Fixpoint,
    Call2Invoke,
    ConstantFold,
    CFGCompactify,
    InlineGetItem,
    InlineGetField,
    DeadCodeElimination,
)
from kirin.dialects import scf, ilist
from kirin.ir.method import Method
from kirin.rewrite.abc import RewriteResult
from kirin.rewrite.cse import CommonSubexpressionElimination
from kirin.passes.aggressive import UnrollScf


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
        )
        result = Fixpoint(Walk(rule)).rewrite(mt.code).join(result)

        return result


@dataclass
class AggressiveUnroll(Pass):
    """A pass to unroll structured control flow"""

    additional_inline_heuristic: Callable[[ir.Statement], bool] = lambda node: True

    fold: Fold = field(init=False)
    typeinfer: TypeInfer = field(init=False)
    scf_unroll: UnrollScf = field(init=False)

    def __post_init__(self):
        self.fold = Fold(self.dialects, no_raise=self.no_raise)
        self.typeinfer = TypeInfer(self.dialects, no_raise=self.no_raise)
        self.scf_unroll = UnrollScf(self.dialects, no_raise=self.no_raise)

    def unsafe_run(self, mt: Method) -> RewriteResult:
        result = RewriteResult()
        result = self.scf_unroll.unsafe_run(mt).join(result)
        result = (
            Walk(Chain(ilist.rewrite.ConstList2IList(), ilist.rewrite.Unroll()))
            .rewrite(mt.code)
            .join(result)
        )
        result = self.typeinfer.unsafe_run(mt).join(result)
        result = self.fold.unsafe_run(mt).join(result)
        result = Walk(Inline(self.inline_heuristic)).rewrite(mt.code).join(result)
        result = Walk(Fixpoint(CFGCompactify())).rewrite(mt.code).join(result)

        rule = Chain(
            CommonSubexpressionElimination(),
            DeadCodeElimination(),
        )
        result = Fixpoint(Walk(rule)).rewrite(mt.code).join(result)

        return result

    def inline_heuristic(self, node: ir.Statement) -> bool:
        """The heuristic to decide whether to inline a function call or not.
        inside loops and if-else, only inline simple functions, i.e.
        functions with a single block
        """
        return not isinstance(
            node.parent_stmt, (scf.For, scf.IfElse)
        ) and self.additional_inline_heuristic(
            node
        )  # always inline calls outside of loops and if-else
