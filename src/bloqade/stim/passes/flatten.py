# Taken from Phillip Weinberg's bloqade-shuttle implementation
from dataclasses import field, dataclass

from kirin import ir
from kirin.passes import Fold, Pass, TypeInfer
from kirin.rewrite import Walk
from kirin.rewrite.abc import RewriteResult
from kirin.dialects.scf.stmts import For
from kirin.dialects.scf.unroll import ForLoop, PickIfElse

from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.stim.passes.simplify_ifs import StimSimplifyIfs
from bloqade.stim.passes.repeat_eligible import get_repeat_range
from bloqade.stim.passes.hint_const_in_loops import HintConstInLoopBodies


class SelectiveForLoop(ForLoop):
    """ForLoop rewrite that skips REPEAT-eligible outermost loops.

    Only the outermost REPEAT-eligible loop is preserved. If a loop is
    nested inside another REPEAT-eligible loop, it gets unrolled.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, For):
            return RewriteResult()
        if get_repeat_range(node) is not None and not self._has_repeat_ancestor(node):
            return RewriteResult()
        return super().rewrite_Statement(node)

    def _has_repeat_ancestor(self, node: For) -> bool:
        """Check if any ancestor scf.For is also REPEAT-eligible."""
        parent = node.parent_stmt
        while parent is not None:
            if isinstance(parent, For) and get_repeat_range(parent) is not None:
                return True
            parent = parent.parent_stmt
        return False


@dataclass
class SelectiveUnrollScf(Pass):
    """Like UnrollScf but uses SelectiveForLoop to skip REPEAT-eligible loops."""

    typeinfer: TypeInfer = field(init=False)
    fold: Fold = field(init=False)

    def __post_init__(self):
        self.typeinfer = TypeInfer(self.dialects, no_raise=self.no_raise)
        self.fold = Fold(self.dialects, no_raise=self.no_raise)

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        result = RewriteResult()
        # Set const hints inside preserved loop bodies so inner loops can be unrolled
        result = Walk(HintConstInLoopBodies()).rewrite(mt.code).join(result)
        result = Walk(PickIfElse()).rewrite(mt.code).join(result)
        result = Walk(SelectiveForLoop()).rewrite(mt.code).join(result)
        result = self.fold.unsafe_run(mt).join(result)
        self.typeinfer.unsafe_run(mt)
        return result


@dataclass
class SelectiveAggressiveUnroll(AggressiveUnroll):
    """AggressiveUnroll that preserves REPEAT-eligible outermost loops."""

    def __post_init__(self):
        super().__post_init__()
        self.scf_unroll = SelectiveUnrollScf(self.dialects, no_raise=self.no_raise)


@dataclass
class Flatten(Pass):

    unroll: SelectiveAggressiveUnroll = field(init=False)
    simplify_if: StimSimplifyIfs = field(init=False)

    def __post_init__(self):
        self.unroll = SelectiveAggressiveUnroll(self.dialects, no_raise=self.no_raise)
        self.simplify_if = StimSimplifyIfs(self.dialects, no_raise=self.no_raise)

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        rewrite_result = RewriteResult()
        rewrite_result = self.simplify_if(mt).join(rewrite_result)
        rewrite_result = self.unroll(mt).join(rewrite_result)
        return rewrite_result
