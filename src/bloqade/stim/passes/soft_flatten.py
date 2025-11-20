# Taken from Phillip Weinberg's bloqade-shuttle implementation
from typing import Callable
from dataclasses import field, dataclass

from kirin import ir
from kirin.passes import Fold, Pass, TypeInfer

# from kirin.passes.aggressive import UnrollScf
from kirin.rewrite import (
    Walk,
    Chain,
    Inline,
    Fixpoint,
    CFGCompactify,
    DeadCodeElimination,
    CommonSubexpressionElimination,
)
from kirin.dialects import scf, ilist
from kirin.rewrite.abc import RewriteResult

# from bloqade.qasm2.passes.fold import AggressiveUnroll
from bloqade.stim.passes.simplify_ifs import StimSimplifyIfs


@dataclass
class AggressiveUnroll(Pass):
    """A pass to unroll structured control flow"""

    additional_inline_heuristic: Callable[[ir.Statement], bool] = lambda node: True

    fold: Fold = field(init=False)
    typeinfer: TypeInfer = field(init=False)
    # scf_unroll: UnrollScf = field(init=False)

    def __post_init__(self):
        self.fold = Fold(self.dialects, no_raise=self.no_raise)
        self.typeinfer = TypeInfer(self.dialects, no_raise=self.no_raise)
        # self.scf_unroll = UnrollScf(self.dialects, no_raise=self.no_raise)

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        result = RewriteResult()
        # result = self.scf_unroll.unsafe_run(mt).join(result)
        result = (
            Walk(Chain(ilist.rewrite.ConstList2IList(), ilist.rewrite.Unroll()))
            .rewrite(mt.code)
            .join(result)
        )
        self.typeinfer.unsafe_run(mt)
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


@dataclass
class SoftFlatten(Pass):
    """
    like standard Flatten but without unrolling to let analysis go into loops
    """

    unroll: AggressiveUnroll = field(init=False)
    simplify_if: StimSimplifyIfs = field(init=False)

    def __post_init__(self):
        self.unroll = AggressiveUnroll(self.dialects, no_raise=self.no_raise)

        # DO NOT USE FOR NOW, TrimUnusedYield call messes up loop structure
        # self.simplify_if = StimSimplifyIfs(self.dialects, no_raise=self.no_raise)

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        rewrite_result = RewriteResult()
        # rewrite_result = self.simplify_if(mt).join(rewrite_result)
        rewrite_result = self.unroll(mt).join(rewrite_result)
        return rewrite_result
