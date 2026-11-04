"""Give emitted Jeff regions explicit arguments for their captured values."""

from dataclasses import field, dataclass

from kirin import ir
from kirin.passes import Pass
from kirin.rewrite import Walk
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.jeff.types import is_linear
from bloqade.jeff.dialects import stmts


@dataclass
class Captures(RewriteRule):
    """Collect external operands with Kirin's walker in first-use order."""

    owner: ir.Statement
    values: dict[ir.SSAValue, None] = field(default_factory=dict)

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Record operands whose defining statement lies outside the region owner."""
        if node is self.owner:
            return RewriteResult()
        for value in node.args:
            defining = (
                value.owner
                if isinstance(value.owner, ir.Statement)
                else value.owner.parent_stmt
            )
            if defining is None or not self.owner.is_ancestor(defining):
                self.values[value] = None
        return RewriteResult()


@dataclass
class IsolateRegions(Pass):
    """Make region captures explicit after wire emission has already supplied quantum outputs."""

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        """Isolate inner regions before their enclosing regions."""
        return Walk(IsolateRegion()).rewrite(mt.code)


class IsolateRegion(RewriteRule):
    """Add captured values as inputs without duplicating existing quantum results."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Give each captured operand a block argument in every region."""
        if not isinstance(node, (stmts.For, stmts.Switch)):
            return RewriteResult()
        captures = Captures(node)
        Walk(captures).rewrite(node)
        outer = tuple(captures.values)
        if not outer:
            return RewriteResult()
        if isinstance(node, stmts.For) and any(
            is_linear(value.type) for value in outer
        ):
            raise ir.ValidationError(
                node, "A wire loop must carry every quantum value explicitly."
            )
        for region in node.regions:
            block = region.blocks[0]
            args = [block.args.append_from(value.type, value.name) for value in outer]
            for value, argument in zip(outer, args, strict=True):
                for use in tuple(value.uses):
                    if region.is_ancestor(use.stmt):
                        use.stmt.args[use.index] = argument
            if isinstance(node, stmts.For):
                terminator = block.last_stmt
                assert isinstance(terminator, stmts.Yield)
                terminator.args = (*terminator.args, *args)
        regions = list(node.regions)
        for region in regions:
            region.detach()
        if isinstance(node, stmts.For):
            made = stmts.For(
                node.start, node.stop, node.step, (*node.state, *outer), regions[0]
            )
        else:
            made = stmts.Switch(
                node.selector, (*node.inputs, *outer), regions[:-1], regions[-1]
            )
        node.replace_by(made)
        return RewriteResult(has_done_something=True)
