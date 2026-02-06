# Taken from Phillip Weinberg's bloqade-shuttle implementation
from typing import Callable
from dataclasses import field, dataclass

from kirin import ir, types
from kirin.passes import Pass, TypeInfer
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
from kirin.dialects.ilist.stmts import Range as IListRange, IListType
from kirin.dialects.ilist.runtime import IList

# from bloqade.qasm2.passes.fold import AggressiveUnroll
from bloqade.stim.passes.simplify_ifs import StimSimplifyIfs

# this fold is different from the one in Kirin
from bloqade.rewrite.passes.aggressive_unroll import Fold as BloqadeFold
from bloqade.rewrite.passes.canonicalize_ilist import CanonicalizeIList


class HintLenInLoops(RewriteRule):
    """Like ilist.rewrite.HintLen but works inside loops.

    The standard HintLen skips py.Len nodes inside scf.For/IfElse to avoid
    issues with dynamically-sized collections. However, for IList with a
    literal length in the type, the length is compile-time constant and
    safe to hint regardless of context.
    """

    def _get_collection_len(self, collection: ir.SSAValue):
        coll_type = collection.type
        if not isinstance(coll_type, types.Generic):
            return None
        if (
            coll_type.is_subseteq(IListType)
            and isinstance(coll_type.vars[1], types.Literal)
            and isinstance(coll_type.vars[1].data, int)
        ):
            return coll_type.vars[1].data
        return None

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, py.Len):
            return RewriteResult()

        if (coll_len := self._get_collection_len(node.value)) is None:
            return RewriteResult()

        existing_hint = node.result.hints.get("const")
        new_hint = const.Value(coll_len)

        if existing_hint is not None and new_hint.is_structurally_equal(existing_hint):
            return RewriteResult()

        node.result.hints["const"] = new_hint
        return RewriteResult(has_done_something=True)


class HintRangeInLoops(RewriteRule):
    """Hint ilist.Range when its arguments are constant.

    Since const propagation doesn't properly wrap hints for values computed
    inside loop bodies, we directly set the const hint on range results when
    we can determine the range value. We check both hints and the defining
    statement (py.Constant) to get the constant value.
    """

    def _get_const_value(self, ssa: ir.SSAValue):
        """Get const value from hint or from defining py.Constant statement."""
        hint = ssa.hints.get("const")
        if isinstance(hint, const.Value):
            return hint.data

        # Check if defined by py.Constant
        owner = ssa.owner
        if isinstance(owner, py.Constant):
            # value is ir.Data (e.g., PyAttr), need to get the actual data
            value = owner.value
            if hasattr(value, "data"):
                return value.data
            return value
        return None

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, IListRange):
            return RewriteResult()

        start_val = self._get_const_value(node.start)
        stop_val = self._get_const_value(node.stop)
        step_val = self._get_const_value(node.step)

        if start_val is None or stop_val is None or step_val is None:
            return RewriteResult()

        range_val = IList(range(start_val, stop_val, step_val), elem=types.Int)
        new_hint = const.Value(range_val)

        existing_hint = node.result.hints.get("const")
        if existing_hint is not None and new_hint.is_structurally_equal(existing_hint):
            return RewriteResult()

        node.result.hints["const"] = new_hint
        return RewriteResult(has_done_something=True)


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
class RestrictedLoopUnroll(Pass):
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

        # equivalent of ScfUnroll but now customized and
        # essentially inlined hear for development purposes
        result = Walk(PickIfElse()).rewrite(mt.code).join(result)
        result = Walk(ForLoopNoIterDependance()).rewrite(mt.code).join(result)
        result = self.fold.unsafe_run(mt).join(result)
        result = self.typeinfer.unsafe_run(mt)  # no join here, avoid fixpoint issues

        # After type inference, IList types have literal lengths. Run fold again
        # to ensure const hints are set on values inside loop bodies.
        result = self.fold.unsafe_run(mt).join(result)

        # Now we can:
        # 1. Hint len() for ILists with literal length (even inside loops)
        # 2. Hint range() when its arguments have const hints
        # 3. Unroll inner loops that now have const iterables
        result = (
            Fixpoint(Walk(Chain(HintLenInLoops(), HintRangeInLoops())))
            .rewrite(mt.code)
            .join(result)
        )
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

    unroll: RestrictedLoopUnroll = field(init=False)
    simplify_if: StimSimplifyIfs = field(init=False)

    def __post_init__(self):
        self.unroll = RestrictedLoopUnroll(self.dialects, no_raise=self.no_raise)
        self.simplify_if = StimSimplifyIfs(self.dialects, no_raise=self.no_raise)

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        rewrite_result = RewriteResult()
        rewrite_result = self.simplify_if(mt).join(rewrite_result)
        rewrite_result = self.unroll(mt).join(rewrite_result)
        return rewrite_result
