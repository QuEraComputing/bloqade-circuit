from dataclasses import field, dataclass

from kirin import ir
from kirin.passes import Fold, Pass, TypeInfer
from kirin.rewrite import (
    Walk,
    Chain,
    Inline,
    Fixpoint,
    Call2Invoke,
    ConstantFold,
    InlineGetItem,
    InlineGetField,
)
from kirin.dialects import ilist
from kirin.rewrite.abc import RewriteResult
from kirin.passes.hint_const import HintConst
from kirin.dialects.scf.stmts import For
from kirin.dialects.scf.unroll import ForLoop, PickIfElse

from bloqade.stim.passes.simplify_ifs import StimSimplifyIfs
from bloqade.stim.passes.repeat_eligible import get_repeat_range
from bloqade.stim.passes.hint_const_in_loops import HintConstInLoops


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
class Flatten(Pass):

    simplify_if: StimSimplifyIfs = field(init=False)
    hint_const: HintConst = field(init=False)
    hint_const_in_loops: HintConstInLoops = field(init=False)
    typeinfer: TypeInfer = field(init=False)

    def __post_init__(self):
        self.simplify_if = StimSimplifyIfs(self.dialects, no_raise=self.no_raise)
        self.hint_const = HintConst(self.dialects, no_raise=self.no_raise)
        self.hint_const_in_loops = HintConstInLoops(
            self.dialects, no_raise=self.no_raise
        )
        self.typeinfer = TypeInfer(self.dialects, no_raise=self.no_raise)

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        result = RewriteResult()

        # --- simplify ifs ---
        result = self.simplify_if(mt).join(result)

        # --- fold constants (needed so get_repeat_range sees const range) ---
        result = self.hint_const.unsafe_run(mt).join(result)
        fold_rule = Chain(
            ConstantFold(),
            Call2Invoke(),
            InlineGetField(),
            InlineGetItem(),
            ilist.rewrite.InlineGetItem(),
            ilist.rewrite.FlattenAdd(),
            ilist.rewrite.HintLen(),
        )
        result = Fixpoint(Walk(fold_rule)).rewrite(mt.code).join(result)

        # --- selective unroll (preserve REPEAT-eligible outer loops) ---
        result = self.hint_const_in_loops.unsafe_run(mt).join(result)
        result = Walk(PickIfElse()).rewrite(mt.code).join(result)
        result = Walk(SelectiveForLoop()).rewrite(mt.code).join(result)

        # --- re-fold + type infer after unrolling ---
        kirin_fold = Fold(self.dialects, no_raise=self.no_raise)
        result = kirin_fold.unsafe_run(mt).join(result)
        self.typeinfer.unsafe_run(mt)

        # --- ilist canonicalization ---
        result = (
            Walk(Chain(ilist.rewrite.ConstList2IList(), ilist.rewrite.Unroll()))
            .rewrite(mt.code)
            .join(result)
        )

        # --- inline function calls ---
        result = Walk(Inline(lambda _: True)).rewrite(mt.code).join(result)

        return result
