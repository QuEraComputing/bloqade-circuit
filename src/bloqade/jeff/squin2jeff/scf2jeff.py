"""Replace kirin loops and branches with Jeff loops and switches."""

from kirin import ir, types
from kirin.dialects import scf
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.dialects.ilist import stmts as ilist_stmts

from bloqade.types import is_subtype
from bloqade.jeff.forms import loop_range
from bloqade.jeff.dialects import stmts

from .kinds import put, fitted, replace, jeff_kind


class ControlFlow(RewriteRule):
    """Replace each `scf.For`, `scf.IfElse` and `scf.Yield` with its Jeff form.

    The walk visits a loop before its body. So each loop body yield finds its Jeff
    loop and fits its values to the state types of that loop.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Rewrite `node` if it is a loop, a branch or the yield of a Jeff region."""
        if isinstance(node, scf.For):
            loop(node)
        elif isinstance(node, scf.IfElse):
            switch(node)
        elif isinstance(node, scf.Yield) and isinstance(node.parent_stmt, stmts.For):
            loop_state = tuple(result.type for result in node.parent_stmt.results)
            yielded(node, loop_state)
        else:
            return RewriteResult()
        return RewriteResult(has_done_something=True)


def separate(node: ir.Statement, values: tuple[ir.SSAValue, ...]) -> None:
    """Reject a tuple among `values`, because Jeff has no tuples."""
    if any(is_subtype(value.type, types.Tuple) for value in values):
        raise ir.ValidationError(
            node, f"a region of {node.name} requires separate scalar or array results"
        )


def loop(node: scf.For) -> None:
    """Replace `node` with a Jeff loop that carries the same state.

    A Jeff loop runs from `start` to `stop` by `step`, so the iterable must be a
    range. The loop body moves over unchanged, and its block arguments take the
    Jeff types of the loop state.
    """
    separate(node, tuple(node.results))
    bounds: tuple[ir.SSAValue, ir.SSAValue, ir.SSAValue]
    match loop_range(node.iterable):
        case ilist_stmts.Range(start=start, stop=stop, step=step):
            bounds = (start, stop, step)
        case range(start=start, stop=stop, step=step):
            bounds = (
                put(stmts.ConstInt(value=start), node).result,
                put(stmts.ConstInt(value=stop), node).result,
                put(stmts.ConstInt(value=step), node).result,
            )
        case _:
            raise ir.ValidationError(node, f"{node.iterable} is not a range")
    region = node.body
    region.detach()
    block = region.blocks[0]
    block.args[0].type = types.Int
    for argument, value in zip(block.args[1:], node.initializers, strict=True):
        argument.type = value.type
    made = put(stmts.For(*bounds, tuple(node.initializers), region), node)
    replace(node, *made.results)


def switch(node: scf.IfElse) -> None:
    """Replace `node` with a Jeff switch on its condition.

    The else body becomes case 0 and the then body the default case. Each body of
    `scf.IfElse` takes the condition as a block argument, and the rewrite replaces
    that argument with the condition itself. A Jeff switch needs a Jeff yield in
    each body when it is built, so this rewrite also replaces each body yield.
    """
    separate(node, tuple(node.results))
    kinds = tuple(jeff_kind(result.type) for result in node.results)
    regions: list[ir.Region] = []
    for body in (node.else_body, node.then_body):
        block = body.blocks[0]
        for argument in tuple(block.args):
            argument.replace_by(node.cond)
            argument.delete()
        end = block.last_stmt
        assert isinstance(end, scf.Yield)
        yielded(end, kinds)
        body.detach()
        regions.append(body)
    made = put(stmts.Switch(node.cond, (), regions[:1], regions[1]), node)
    for result, kind in zip(made.results, kinds, strict=True):
        result.type = kind
    replace(node, *made.results)


def yielded(node: scf.Yield, kinds: tuple[types.TypeAttribute, ...]) -> None:
    """Replace the region yield `node` with a Jeff yield of values of the types `kinds`."""
    if len(node.values) != len(kinds):
        raise ir.ValidationError(
            node, "The region yield must match its declared result count."
        )
    separate(node, tuple(node.values))
    values = tuple(
        fitted(value, kind, node)
        for value, kind in zip(node.values, kinds, strict=True)
    )
    put(stmts.Yield(*values), node)
    node.delete()
