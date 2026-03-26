"""Set const hints on py.Constant statements inside preserved scf.For bodies.

HintConst only exposes the top-level const propagation frame, so SSA values
inside scf.For bodies don't get const hints. This pass directly sets hints
on py.Constant statements (which are trivially constant) and propagates
hints from initializers to body block args, enabling ConstantFold and
other passes to work inside preserved loop bodies.
"""

from kirin import ir, types
from kirin.analysis import const
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.dialects.scf.stmts import For
from kirin.dialects.ilist.stmts import New as IListNew, Range as IListRange, IListType

from bloqade.stim.passes.repeat_eligible import get_repeat_range


class HintConstInLoopBodies(RewriteRule):
    """Set const hints on statements inside preserved scf.For bodies.

    HintConst doesn't propagate into scf.For body frames, so we manually:
    - Set const hints on py.Constant results (trivially constant)
    - Set const hints on py.tuple.New / py.ilist.New when all args are const
    - Propagate hints from initializers to body block args
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
            # Fix degraded types on block args
            if isinstance(
                block_arg.type, (types.BottomType, types.AnyType)
            ) and not isinstance(init.type, (types.BottomType, types.AnyType)):
                block_arg.type = init.type
                has_done_something = True

        # Propagate hints and types from initializers to scf.For results.
        # The results represent the final loop state. For REPEAT-eligible
        # loops, propagating the initializer's type prevents BottomType
        # from degrading downstream type chains (e.g., for accumulators).
        for result, init in zip(node.results, node.initializers):
            for key, value in init.hints.items():
                if key not in result.hints:
                    result.hints[key] = value
                    has_done_something = True
            # Propagate type from initializer if result type is degraded
            # (BottomType, Union, AnyType) and initializer has a concrete type.
            # Also propagate through GetItem and ilist.New chains so
            # downstream SetDetectorPartial sees valid types.
            if not result.type.is_subseteq(init.type) and not isinstance(
                init.type, (types.BottomType, types.AnyType)
            ):
                result.type = init.type
                has_done_something = True
                self._propagate_type_through_uses(result)

        # Set const hints on statements inside the body
        for stmt in body_block.stmts:
            if self._hint_stmt(stmt):
                has_done_something = True

        return RewriteResult(has_done_something=has_done_something)

    def _propagate_type_through_uses(self, value: ir.SSAValue) -> None:
        """Propagate types through GetItem and ilist.New chains."""
        for use in value.uses:
            stmt = use.stmt
            if isinstance(stmt, py.GetItem) and isinstance(
                stmt.result.type, (types.BottomType, types.AnyType)
            ):
                # GetItem on IList[T, N] should produce T
                if hasattr(value.type, "vars") and len(value.type.vars) > 0:
                    stmt.result.type = value.type.vars[0]
                    # Continue propagation
                    self._propagate_type_through_uses(stmt.result)
            elif isinstance(stmt, IListNew):
                # ilist.New result type depends on element types
                # Just set it to IList[elem_type, Literal(len)]
                elem_types = [v.type for v in stmt.values]
                if elem_types and not any(
                    isinstance(t, types.BottomType) for t in elem_types
                ):
                    stmt.result.type = IListType[
                        elem_types[0], types.Literal(len(elem_types))
                    ]

    def _hint_stmt(self, stmt: ir.Statement) -> bool:
        """Set const hint on a statement's result if possible. Returns True if changed."""
        if not stmt.results or "const" in stmt.results[0].hints:
            return False

        # py.Constant is trivially constant
        if isinstance(stmt, py.Constant):
            stmt.result.hints["const"] = const.Value(stmt.value.unwrap())
            return True

        # py.tuple.New: constant if all args are const
        if isinstance(stmt, py.tuple.New):
            arg_vals = []
            for arg in stmt.args:
                h = arg.hints.get("const")
                if not isinstance(h, const.Value):
                    return False
                arg_vals.append(h.data)
            stmt.result.hints["const"] = const.Value(tuple(arg_vals))
            return True

        # ilist.New: constant if all args are const
        if isinstance(stmt, IListNew):
            arg_vals = []
            for arg in stmt.values:
                h = arg.hints.get("const")
                if not isinstance(h, const.Value):
                    return False
                arg_vals.append(h.data)
            from kirin.dialects.ilist.runtime import IList

            stmt.result.hints["const"] = const.Value(IList(arg_vals))
            return True

        # py.Len: constant if the collection has IList type with Literal length
        if isinstance(stmt, py.Len):
            coll_type = stmt.value.type
            if (
                isinstance(coll_type, types.Generic)
                and coll_type.is_subseteq(IListType)
                and isinstance(coll_type.vars[1], types.Literal)
                and isinstance(coll_type.vars[1].data, int)
            ):
                stmt.result.hints["const"] = const.Value(coll_type.vars[1].data)
                return True
            return False

        # ilist.Range / py.Range: constant if start/stop/step are const
        if isinstance(stmt, (IListRange, py.range.Range)):
            start_h = stmt.start.hints.get("const")
            stop_h = stmt.stop.hints.get("const")
            step_h = stmt.step.hints.get("const")
            if (
                isinstance(start_h, const.Value)
                and isinstance(stop_h, const.Value)
                and isinstance(step_h, const.Value)
            ):
                r = range(start_h.data, stop_h.data, step_h.data)
                from kirin.dialects.ilist.runtime import IList

                stmt.result.hints["const"] = const.Value(IList(r))
                return True

        return False
