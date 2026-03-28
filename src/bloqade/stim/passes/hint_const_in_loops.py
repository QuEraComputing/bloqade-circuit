"""Set const hints on statements inside preserved scf.For bodies.

HintConst only exposes the top-level const propagation frame, so SSA values
inside scf.For bodies don't get const hints. This module provides individual
rewrite rules for hinting specific statement types, a rule for propagating
initializer hints into loop bodies, and a Pass that composes them all.
"""

from dataclasses import dataclass

from kirin import ir, types
from kirin.rewrite import Walk, Chain
from kirin.analysis import const
from kirin.dialects import py
from kirin.passes.abc import Pass
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.dialects.scf.stmts import For
from kirin.dialects.ilist.stmts import New as IListNew, Range as IListRange, IListType

from bloqade.stim.passes.repeat_eligible import get_repeat_range
from bloqade.stim.passes.constprop_override import install as install_constprop_override


class HintConstant(RewriteRule):
    """Hint py.Constant results as const (trivially constant)."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, py.Constant):
            return RewriteResult()
        if not node.results or "const" in node.results[0].hints:
            return RewriteResult()
        node.result.hints["const"] = const.Value(node.value.unwrap())
        return RewriteResult(has_done_something=True)


class HintTupleNew(RewriteRule):
    """Hint py.tuple.New results as const when all args are const."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, py.tuple.New):
            return RewriteResult()
        if not node.results or "const" in node.results[0].hints:
            return RewriteResult()
        arg_vals = []
        for arg in node.args:
            h = arg.hints.get("const")
            if not isinstance(h, const.Value):
                return RewriteResult()
            arg_vals.append(h.data)
        node.result.hints["const"] = const.Value(tuple(arg_vals))
        return RewriteResult(has_done_something=True)


class HintIListNew(RewriteRule):
    """Hint ilist.New results as const when all values are const."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, IListNew):
            return RewriteResult()
        if not node.results or "const" in node.results[0].hints:
            return RewriteResult()
        arg_vals = []
        for arg in node.values:
            h = arg.hints.get("const")
            if not isinstance(h, const.Value):
                return RewriteResult()
            arg_vals.append(h.data)
        from kirin.dialects.ilist.runtime import IList

        node.result.hints["const"] = const.Value(IList(arg_vals))
        return RewriteResult(has_done_something=True)


class HintLen(RewriteRule):
    """Hint py.Len results as const when the collection has IList type with Literal length."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, py.Len):
            return RewriteResult()
        if not node.results or "const" in node.results[0].hints:
            return RewriteResult()
        coll_type = node.value.type
        if (
            isinstance(coll_type, types.Generic)
            and coll_type.is_subseteq(IListType)
            and isinstance(coll_type.vars[1], types.Literal)
            and isinstance(coll_type.vars[1].data, int)
        ):
            node.result.hints["const"] = const.Value(coll_type.vars[1].data)
            return RewriteResult(has_done_something=True)
        return RewriteResult()


class HintRange(RewriteRule):
    """Hint ilist.Range / py.range.Range results as const when start/stop/step are const."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, (IListRange, py.range.Range)):
            return RewriteResult()
        if not node.results or "const" in node.results[0].hints:
            return RewriteResult()
        start_h = node.start.hints.get("const")
        stop_h = node.stop.hints.get("const")
        step_h = node.step.hints.get("const")
        if (
            isinstance(start_h, const.Value)
            and isinstance(stop_h, const.Value)
            and isinstance(step_h, const.Value)
        ):
            r = range(start_h.data, stop_h.data, step_h.data)
            from kirin.dialects.ilist.runtime import IList

            node.result.hints["const"] = const.Value(IList(r))
            return RewriteResult(has_done_something=True)
        return RewriteResult()


class PropagateInitializerHints(RewriteRule):
    """Propagate hints and types from For loop initializers to body block args and results.

    Only applies to REPEAT-eligible For loops. Also propagates types through
    downstream GetItem and ilist.New use chains.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, For):
            return RewriteResult()
        if get_repeat_range(node) is None:
            return RewriteResult()

        has_done_something = False

        # Propagate hints and types from initializers to body block args
        body_block = node.body.blocks[0]
        for block_arg, init in zip(body_block.args[1:], node.initializers):
            for key, value in init.hints.items():
                if key not in block_arg.hints:
                    block_arg.hints[key] = value
                    has_done_something = True
            if isinstance(
                block_arg.type, (types.BottomType, types.AnyType)
            ) and not isinstance(init.type, (types.BottomType, types.AnyType)):
                block_arg.type = init.type
                has_done_something = True

        # Propagate hints and types from initializers to scf.For results
        for result, init in zip(node.results, node.initializers):
            for key, value in init.hints.items():
                if key not in result.hints:
                    result.hints[key] = value
                    has_done_something = True
            if not result.type.is_subseteq(init.type) and not isinstance(
                init.type, (types.BottomType, types.AnyType)
            ):
                result.type = init.type
                has_done_something = True
                _propagate_type_through_uses(result)

        return RewriteResult(has_done_something=has_done_something)


def _propagate_type_through_uses(value: ir.SSAValue) -> None:
    """Propagate types through GetItem and ilist.New chains."""
    for use in value.uses:
        stmt = use.stmt
        if isinstance(stmt, py.GetItem) and isinstance(
            stmt.result.type, (types.BottomType, types.AnyType)
        ):
            if hasattr(value.type, "vars") and len(value.type.vars) > 0:
                stmt.result.type = value.type.vars[0]
                _propagate_type_through_uses(stmt.result)
        elif isinstance(stmt, IListNew):
            elem_types = [v.type for v in stmt.values]
            if elem_types and not any(
                isinstance(t, types.BottomType) for t in elem_types
            ):
                stmt.result.type = IListType[
                    elem_types[0], types.Literal(len(elem_types))
                ]


@dataclass
class HintConstInLoops(Pass):
    """Pass that sets const hints inside preserved scf.For loop bodies.

    Composes PropagateInitializerHints (for For-level hint/type propagation)
    with per-statement hinting rules (HintConstant, HintTupleNew, etc.).
    Also installs the early-terminating constprop override for scf.For.
    """

    def __post_init__(self):
        install_constprop_override()

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        result = Walk(PropagateInitializerHints()).rewrite(mt.code)
        result = (
            Walk(
                Chain(
                    HintConstant(),
                    HintTupleNew(),
                    HintIListNew(),
                    HintLen(),
                    HintRange(),
                )
            )
            .rewrite(mt.code)
            .join(result)
        )
        return result
