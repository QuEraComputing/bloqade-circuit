"""This module holds `isolate_regions`, which makes each jeff region take its outer values."""

from kirin import ir

from bloqade.jeff.types import is_linear
from bloqade.jeff.dialects import stmts


def isolate_regions(code: ir.Statement) -> None:
    """Make every jeff loop and switch in `code` take the outer values that it reads.

    The emitter fills a region that reads outer values and outer wires directly,
    and the code after the region keeps using the outer wires. For each loop and
    switch, innermost first, this pass makes each outer value an input and a block
    argument of every region. Each region yields the value back, and a wire comes
    back as its last version in the region. The code after the statement then
    reads the result in place of the outer wire.
    """
    nodes = [
        node for node in code.walk() if isinstance(node, (stmts.For, stmts.Switch))
    ]
    for node in sorted(nodes, key=_depth, reverse=True):
        _isolate(node)


def _depth(node: ir.Statement) -> int:
    """Return the number of statements that enclose `node`."""
    depth = 0
    parent = node.parent_stmt
    while parent is not None:
        depth += 1
        parent = parent.parent_stmt
    return depth


def _outer_values(node: ir.Statement) -> list[ir.SSAValue]:
    """Return the values that the regions of `node` read and define outside `node`.

    The values come in the order of their first use.
    """
    found: dict[ir.SSAValue, None] = {}
    for region in node.regions:
        for inner in region.walk():
            if not isinstance(inner, ir.Statement):
                continue
            for value in inner.args:
                if not _defined_in(node, value):
                    found[value] = None
    return list(found)


def _defined_in(node: ir.Statement, value: ir.SSAValue) -> bool:
    """Return True if `node` or one of its regions defines `value`."""
    match value:
        case ir.ResultValue(owner=owner):
            return node.is_ancestor(owner)
        case ir.BlockArgument(owner=block) if block.parent_stmt is not None:
            return node.is_ancestor(block.parent_stmt)
    return False


def _last(wire: ir.SSAValue, block: ir.Block) -> ir.SSAValue:
    """Return the last version of `wire` in `block`.

    A statement that consumes its k-th wire operand gives the next version as its
    k-th wire result.
    """
    while True:
        uses = [use for use in wire.uses if use.stmt.parent_block is block]
        if not uses or isinstance(uses[0].stmt, stmts.Yield):
            return wire
        (use,) = uses
        operands = [arg for arg in use.stmt.args if is_linear(arg.type)]
        results = [res for res in use.stmt.results if is_linear(res.type)]
        position = operands.index(wire)
        if position >= len(results):
            raise ValueError(f"'{use.stmt.name}' consumes an outer wire for good")
        wire = results[position]


def _isolate(node: ir.Statement) -> None:
    """Make `node` take each outer value as an input and hand each wire back."""
    outer = _outer_values(node)
    if not outer:
        return
    for region in node.regions:
        block = region.blocks[0]
        args = [block.args.append_from(value.type, value.name) for value in outer]
        for value, arg in zip(outer, args):
            for use in list(value.uses):
                if region.is_ancestor(use.stmt):
                    use.stmt.args[use.index] = arg
        terminator = block.last_stmt
        assert isinstance(terminator, stmts.Yield)
        back = [_last(arg, block) if is_linear(arg.type) else arg for arg in args]
        terminator.args = (*terminator.args, *back)
    made = _rebuilt(node, outer)
    made.insert_before(node)
    for old, new in zip(node.results, made.results):
        old.replace_by(new)
    node.delete()
    returned = made.results[len(made.results) - len(outer) :]
    for value, result in zip(outer, returned):
        if is_linear(value.type):
            _reads_after(made, value, result)


def _rebuilt(node: ir.Statement, outer: list[ir.SSAValue]) -> ir.Statement:
    """Return a copy of the loop or switch `node` that also takes `outer`."""
    regions = list(node.regions)
    for region in regions:
        region.detach()
    if isinstance(node, stmts.For):
        state = (*node.state, *outer)
        return stmts.For(node.start, node.stop, node.step, state, regions[0])
    assert isinstance(node, stmts.Switch)
    *branches, default = regions
    return stmts.Switch(node.selector, (*node.inputs, *outer), branches, default)


def _reads_after(node: ir.Statement, wire: ir.SSAValue, result: ir.SSAValue) -> None:
    """Make the code after `node` in its block read `result` in place of `wire`."""
    block = node.parent_block
    later: set[ir.Statement] = set()
    stmt = node.next_stmt
    while stmt is not None:
        later.add(stmt)
        stmt = stmt.next_stmt
    for use in list(wire.uses):
        top = use.stmt
        while top.parent_block is not block and top.parent_stmt is not None:
            top = top.parent_stmt
        if top in later:
            use.stmt.args[use.index] = result
