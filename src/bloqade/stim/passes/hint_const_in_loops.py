"""Set const hints on statements inside preserved scf.For bodies.

The standard kirin pipeline runs ``const.Propagate`` once at the top-level
method scope, so SSA values inside preserved scf.For bodies don't pick up
const hints. This module fills that gap with a generic rule that mimics
``const.Propagate``'s pure-fallback logic (run each ``Pure`` statement's
concrete impl on its const-hinted args, stamp the result back as a const
hint), plus a few specialized rules for cases that need static-type info
or scf.For-aware traversal.
"""

from dataclasses import dataclass

from kirin import ir, types, interp
from kirin.rewrite import Walk, Chain
from kirin.analysis import const
from kirin.dialects import py
from kirin.passes.abc import Pass
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.dialects.scf.stmts import For, Yield
from kirin.dialects.ilist.stmts import New as IListNew, IListType

from bloqade.stim.passes.repeat_eligible import get_repeat_range


@dataclass
class HintPureFromConcrete(RewriteRule):
    """Generic const-folder mimicking ``const.Propagate``'s pure fallback.

    For any ``Pure`` statement whose args all carry ``const.Value`` hints,
    run the concrete impl on the const data and stamp each result with a
    ``const.Value`` hint. Subsumes per-stmt hand-rolled folders for
    Constant, TupleNew, IListNew, Range, Slice, USub, and similar.
    """

    dialects: ir.DialectGroup

    def __post_init__(self):
        self._interp = interp.Interpreter(self.dialects)
        self._interp.initialize()

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not node.has_trait(ir.Pure):
            return RewriteResult()
        if not node.results:
            return RewriteResult()
        if all("const" in r.hints for r in node.results):
            return RewriteResult()
        arg_data = []
        for arg in node.args:
            h = arg.hints.get("const")
            if not isinstance(h, const.Value):
                return RewriteResult()
            arg_data.append(h.data)
        _frame = self._interp.initialize_frame(node)
        _frame.set_values(node.args, tuple(arg_data))
        method = self._interp.lookup_registry(_frame, node)
        if method is None:
            return RewriteResult()
        ret = method(self._interp, _frame, node)
        if not isinstance(ret, tuple) or len(ret) != len(node.results):
            return RewriteResult()
        changed = False
        for result, v in zip(node.results, ret):
            if "const" not in result.hints:
                result.hints["const"] = const.Value(v)
                changed = True
        return RewriteResult(has_done_something=changed)


class HintLen(RewriteRule):
    """Hint py.Len results as const from static IList type info.

    Kept distinct from ``HintPureFromConcrete`` because the length comes
    from the operand's *type* (``IList[X, Literal(N)]``), not from a
    const-hinted operand value — useful when the IList itself isn't const
    but its length is statically known.
    """

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

        # Determine which iter_args are loop-invariant (yield value == block arg)
        yield_stmt = body_block.last_stmt
        loop_invariant = set()
        if isinstance(yield_stmt, Yield):
            for i, (block_arg, yield_val) in enumerate(
                zip(body_block.args[1:], yield_stmt.values)
            ):
                if yield_val is block_arg:
                    loop_invariant.add(i)

        # Propagate types from initializers to scf.For results (always safe),
        # but only propagate const hints for loop-invariant iter_args (where
        # the body doesn't modify the value).
        for i, (result, init) in enumerate(zip(node.results, node.initializers)):
            if i in loop_invariant:
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


def _propagate_type_through_uses(
    value: ir.SSAValue,
    delta_K: int | None = None,
    delta_elem: types.TypeAttribute | None = None,
) -> None:
    """Propagate types through GetItem, ilist.New, and concat-Add chains.

    ``delta_K`` and ``delta_elem`` describe an iter-arg-grown accumulator
    (``acc = acc + ms`` or ``acc = ms + acc`` with ``len(ms) = K`` and
    ``ms`` element type ``delta_elem``). When provided:

    - Slice GetItem with the REPEAT-faithful shapes ``[-K:]`` (append) or
      ``[:K]`` (prepend) is refined to ``IList[elem, Literal(K)]``;
      non-faithful slices fall back to ``IList[elem, Any]``.
    - py.Add results consuming the iter_arg (the post-concat ``acc + ms``
      SSA) are refined to ``IList[delta_elem, Any]`` so downstream uses
      (GetItem, IListNew) can be typed correctly.
    """
    for use in value.uses:
        stmt = use.stmt
        if isinstance(stmt, py.GetItem):
            if not (hasattr(value.type, "vars") and len(value.type.vars) > 0):
                continue
            elem_type = value.type.vars[0]
            idx_hint = stmt.index.hints.get("const")
            idx_const = idx_hint.data if isinstance(idx_hint, const.Value) else None
            if isinstance(idx_const, slice):
                slice_len = (
                    _faithful_slice_length(idx_const, delta_K)
                    if delta_K is not None
                    else None
                )
                if slice_len is None:
                    continue
                new_type = IListType[elem_type, types.Literal(slice_len)]
                if new_type != stmt.result.type:
                    stmt.result.type = new_type
                    _propagate_type_through_uses(stmt.result, delta_K, delta_elem)
            elif isinstance(stmt.result.type, (types.BottomType, types.AnyType)):
                stmt.result.type = elem_type
                _propagate_type_through_uses(stmt.result, delta_K, delta_elem)
        elif isinstance(stmt, IListNew):
            elem_types = [v.type for v in stmt.values]
            if elem_types and not any(
                isinstance(t, types.BottomType) for t in elem_types
            ):
                stmt.result.type = IListType[
                    elem_types[0], types.Literal(len(elem_types))
                ]
        elif isinstance(stmt, py.Add) and delta_elem is not None:
            current = stmt.result.type
            if isinstance(current, types.Generic) and len(current.vars) >= 2:
                length = current.vars[1]
            else:
                length = types.Any
            new_type = IListType[delta_elem, length]
            if new_type != current:
                stmt.result.type = new_type
                _propagate_type_through_uses(stmt.result, delta_K, delta_elem)


def _faithful_slice_length(s: slice, K: int) -> int | None:
    """Static length for slices of an iter-arg-grown accumulator that are
    REPEAT-faithful: each iteration's slice references the same K positions
    relative to the iteration's emit point. Recognized shapes:

    - ``acc[-K:]``: last K elements (append-grown accumulator)
    - ``acc[:K]``: first K elements (prepend-grown accumulator)
    """
    if s.step is not None and s.step != 1:
        return None
    if s.start == -K and s.stop is None:
        return K
    if (s.start is None or s.start == 0) and s.stop == K:
        return K
    return None


def _detect_concat_yield_delta(
    yield_val: ir.SSAValue, iter_arg: ir.BlockArgument
) -> tuple[types.TypeAttribute, int] | None:
    """Return ``(ms_elem_type, K)`` if ``yield_val`` is ``iter_arg + ms``
    or ``ms + iter_arg`` with ``ms`` of statically-known IList length.
    """
    if not isinstance(yield_val, ir.ResultValue):
        return None
    owner = yield_val.owner
    if not isinstance(owner, py.Add):
        return None
    if owner.lhs is iter_arg:
        ms = owner.rhs
    elif owner.rhs is iter_arg:
        ms = owner.lhs
    else:
        return None
    ms_type = ms.type
    if not (
        isinstance(ms_type, types.Generic)
        and ms_type.is_subseteq(IListType)
        and isinstance(ms_type.vars[1], types.Literal)
        and isinstance(ms_type.vars[1].data, int)
    ):
        return None
    return ms_type.vars[0], ms_type.vars[1].data


class PropagateBodyArgTypes(RewriteRule):
    """For preserved scf.For loops where an iter_arg follows the concat
    accumulator pattern (``acc = acc + ms`` or ``acc = ms + acc``), refine
    the body block arg's type to ``IList[ms_elem_type, Any]`` and propagate
    through in-body uses. Enables partial rewrites to recognize fixed-size
    list literals and REPEAT-faithful slices derived from the accumulator
    (e.g., ``[acc[-1]]``, ``acc[-2:]``).
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, For):
            return RewriteResult()
        if get_repeat_range(node) is None:
            return RewriteResult()

        body_block = node.body.blocks[0]
        yield_stmt = body_block.last_stmt
        if not isinstance(yield_stmt, Yield):
            return RewriteResult()

        has_done = False
        for i, block_arg in enumerate(body_block.args[1:]):
            if i >= len(yield_stmt.values):
                continue
            yield_val = yield_stmt.values[i]
            delta = _detect_concat_yield_delta(yield_val, block_arg)
            if delta is None:
                continue
            ms_elem_type, delta_K = delta
            new_type = IListType[ms_elem_type, types.Any]
            if new_type != block_arg.type:
                block_arg.type = new_type
                _propagate_type_through_uses(block_arg, delta_K, ms_elem_type)
                has_done = True

        return RewriteResult(has_done_something=has_done)


@dataclass
class HintConstInLoops(Pass):
    """Pass that sets const hints inside preserved scf.For loop bodies.

    Composes PropagateInitializerHints (for For-level hint/type propagation)
    with per-statement hinting rules (HintConstant, HintTupleNew, etc.).
    Also installs the early-terminating constprop override for scf.For.
    """

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        result = Walk(PropagateInitializerHints()).rewrite(mt.code)
        result = (
            Walk(
                Chain(
                    HintPureFromConcrete(self.dialects),
                    HintLen(),
                )
            )
            .rewrite(mt.code)
            .join(result)
        )
        result = Walk(PropagateBodyArgTypes()).rewrite(mt.code).join(result)
        return result
