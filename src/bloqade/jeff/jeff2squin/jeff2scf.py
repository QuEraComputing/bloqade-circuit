"""This module holds the pass that rewrites jeff control flow as kirin `scf`."""

from dataclasses import dataclass
from collections.abc import Sequence

from kirin import ir, types
from kirin.passes import Pass
from kirin.rewrite import Walk, Chain
from kirin.dialects import py, scf
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.dialects.ilist import stmts as ilist_stmts

from bloqade.jeff.types import is_subtype
from bloqade.jeff.dialects import stmts


class _For(RewriteRule):
    """A rewrite rule that replaces a jeff `for` with an `scf.for` over a range."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Replace `node` if it is a jeff `for`."""
        if not isinstance(node, stmts.For):
            return RewriteResult()
        iterable = ilist_stmts.Range(node.start, node.stop, node.step)
        iterable.insert_before(node)
        body = node.body
        body.detach()
        body.blocks[0].args[0].type = types.Int
        node.replace_by(scf.For(iterable.result, body, *node.state))
        return RewriteResult(has_done_something=True)


class _Switch(RewriteRule):
    """A rewrite rule that replaces a jeff `switch` with nested `scf.if` statements.

    A switch without branches becomes its default block. A one-branch switch on a bit
    becomes one `scf.if` whose then-block is the default.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Replace `node` if it is a jeff `switch`."""
        if not isinstance(node, stmts.Switch):
            return RewriteResult()
        blocks = [region.blocks[0] for region in node.regions if region.blocks]
        if len(blocks) != len(node.regions) or any(
            len(block.args) != len(node.inputs) for block in blocks
        ):
            return RewriteResult()
        if not node.branches:
            block = node.default.blocks[0]
            terminator = block.last_stmt
            if not isinstance(terminator, (stmts.Yield, scf.Yield)) or len(
                terminator.values
            ) != len(node.results):
                return RewriteResult()
            for arg, value in zip(list(block.args), node.inputs):
                arg.replace_by(value)
            for stmt in list(block.stmts):
                if stmt is terminator:
                    break
                stmt.detach()
                stmt.insert_before(node)
            for result, value in zip(node.results, terminator.values):
                result.replace_by(value)
            node.delete()
        elif is_subtype(node.selector.type, types.Bool) and len(node.branches) == 1:
            then, else_ = node.default.blocks[0], node.branches[0].blocks[0]
            for block in (then, else_):
                _rebind(block, node.inputs)
            node.replace_by(
                scf.IfElse(node.selector, ir.Region(then), ir.Region(else_))
            )
        else:
            branches = [region.blocks[0] for region in node.regions]
            for block in branches:
                _rebind(block, node.inputs)
            prelude, top = _chain(node.selector, branches[:-1], branches[-1], 0)
            for stmt in prelude:
                stmt.insert_before(node)
            node.replace_by(top)
        return RewriteResult(has_done_something=True)


class _Yield(RewriteRule):
    """A rewrite rule that replaces a jeff `yield` with an `scf.yield`."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Replace `node` if it is a jeff `yield`."""
        if not isinstance(node, stmts.Yield):
            return RewriteResult()
        node.replace_by(scf.Yield(*node.values))
        return RewriteResult(has_done_something=True)


@dataclass
class JeffToScf(Pass):
    """A pass that rewrites jeff `for` and `switch` as kirin `scf` statements."""

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        """Rewrite every control-flow statement of `mt` in place."""
        return Walk(Chain(_For(), _Switch(), _Yield())).rewrite(mt.code)


def _rebind(block: ir.Block, inputs: Sequence[ir.SSAValue]) -> None:
    """Turn a switch block into an `scf.if` body that reads `inputs`."""
    for arg, value in zip(list(block.args), inputs):
        arg.replace_by(value)
        block.args.delete(arg)
    block.args.insert_from(0, types.Bool, "cond")
    block.detach()


def _chain(
    selector: ir.SSAValue, branches: list[ir.Block], default: ir.Block, case: int
) -> tuple[list[ir.Statement], scf.IfElse]:
    """Build an `scf.if` chain that runs the branch whose index equals `selector`.

    If no index matches, the chain runs the default.
    """
    index = py.Constant(case)
    matches = py.cmp.Eq(selector, index.result)
    if case + 1 < len(branches):
        else_block = ir.Block()
        else_block.args.append_from(types.Bool, "cond")
        prelude, inner = _chain(selector, branches, default, case + 1)
        for stmt in (*prelude, inner):
            else_block.stmts.append(stmt)
        else_block.stmts.append(scf.Yield(*inner.results))
    else:
        else_block = default
    top = scf.IfElse(matches.result, ir.Region(branches[case]), ir.Region(else_block))
    return [index, matches], top
