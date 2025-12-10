# Taken from Phillip Weinberg's bloqade-shuttle implementation
from typing import Callable
from dataclasses import field, dataclass

from kirin import ir
from kirin.passes import Pass, TypeInfer

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
from kirin.analysis import const
from kirin.dialects import py, scf, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.dialects.scf.unroll import PickIfElse

# from bloqade.qasm2.passes.fold import AggressiveUnroll
from bloqade.stim.passes.simplify_ifs import StimSimplifyIfs

# this fold is different from the one in Kirin
from bloqade.rewrite.passes.aggressive_unroll import Fold as BloqadeFold
from bloqade.rewrite.passes.canonicalize_ilist import CanonicalizeIList


class ForLoopNoIterDependance(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, scf.For):
            return RewriteResult()

        # If the iterator is not being depended on at all,
        # take that as a sign that REPEAT should be generated.
        # If the iterator IS being dependent on, we can to fall back
        # to unrolling.
        if not bool(node.body.blocks[0].args[0].uses):
            return RewriteResult()

        # TODO: support for PartialTuple and IList with known length
        if not isinstance(hint := node.iterable.hints.get("const"), const.Value):
            return RewriteResult()

        loop_vars = node.initializers
        for item in hint.data:
            body = node.body.clone()
            block = body.blocks[0]
            item_stmt = py.Constant(item)
            item_stmt.insert_before(node)
            block.args[0].replace_by(item_stmt.result)
            for var, input in zip(block.args[1:], loop_vars):
                var.replace_by(input)

            block_stmt = block.first_stmt
            while block_stmt and not block_stmt.has_trait(ir.IsTerminator):
                block_stmt.detach()
                block_stmt.insert_before(node)
                block_stmt = block.first_stmt

            terminator = block.last_stmt
            # we assume Yield has the same # of values as initializers
            # TODO: check this in validation
            if isinstance(terminator, scf.Yield):
                loop_vars = terminator.values
                terminator.delete()

        for result, output in zip(node.results, loop_vars):
            result.replace_by(output)
        node.delete()
        return RewriteResult(has_done_something=True)


@dataclass
class UnrollNoLoops(Pass):
    """A pass to unroll structured control flow"""

    additional_inline_heuristic: Callable[[ir.Statement], bool] = lambda node: True

    fold: BloqadeFold = field(init=False)
    typeinfer: TypeInfer = field(init=False)
    # scf_unroll: UnrollScf = field(init=False)
    canonicalize_ilist: CanonicalizeIList = field(init=False)

    def __post_init__(self):
        self.fold = BloqadeFold(self.dialects, no_raise=self.no_raise)
        self.typeinfer = TypeInfer(self.dialects, no_raise=self.no_raise)
        self.canonicalize_ilist = CanonicalizeIList(
            self.dialects, no_raise=self.no_raise
        )

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:

        result = RewriteResult()
        result = self.fold.unsafe_run(mt).join(result)

        # equivalent of ScfUnroll but now customized
        result = Walk(PickIfElse()).rewrite(mt.code).join(result)
        result = Walk(ForLoopNoIterDependance()).rewrite(mt.code).join(result)

        # Do not join result of typeinfer or fixpoint will waste time
        result = (
            Walk(Chain(ilist.rewrite.ConstList2IList(), ilist.rewrite.Unroll()))
            .rewrite(mt.code)
            .join(result)
        )
        result = Walk(Inline(self.inline_heuristic)).rewrite(mt.code).join(result)
        result = Walk(Fixpoint(CFGCompactify())).rewrite(mt.code).join(result)
        result = self.canonicalize_ilist.fixpoint(mt).join(result)
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
class FlattenExceptLoops(Pass):
    """
    like standard Flatten but without unrolling to let analysis go into loops
    """

    unroll: UnrollNoLoops = field(init=False)
    simplify_if: StimSimplifyIfs = field(init=False)

    def __post_init__(self):
        self.unroll = UnrollNoLoops(self.dialects, no_raise=self.no_raise)
        self.simplify_if = StimSimplifyIfs(self.dialects, no_raise=self.no_raise)

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        rewrite_result = RewriteResult()
        rewrite_result = self.simplify_if(mt).join(rewrite_result)
        rewrite_result = self.unroll(mt).join(rewrite_result)
        return rewrite_result
