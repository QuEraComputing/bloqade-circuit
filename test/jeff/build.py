"""Build jeff programs as dialect IR for tests.

A program is one entry block of jeff statements inside a `func.Function`.
`entry` starts the block.
`add` appends a statement and returns it.
`method` ends the block with a return and wraps it in a jeff method.
`for_loop`, `switch` and `while_loop` build control-flow statements.
Each of them takes callables that fill a body block.
Each callable returns the values that its block yields.
"""

from typing import TypeVar
from collections.abc import Callable, Sequence

from kirin import ir, types
from kirin.dialects import func

from bloqade.jeff.dialects import stmts, kernel

_S = TypeVar("_S", bound=ir.Statement)


def entry(*input_types: types.TypeAttribute) -> tuple[ir.Block, list[ir.BlockArgument]]:
    """Start a fresh entry block.

    The first argument is `self`, as kirin expects.
    One argument follows for each input type.
    """
    block = ir.Block()
    block.args.append_from(types.Any, "self")
    args = [block.args.append_from(t, "arg") for t in input_types]
    return block, args


def add(block: ir.Block, stmt: _S) -> _S:
    """Append a statement to a block and return it."""
    block.stmts.append(stmt)
    return stmt


def method(
    block: ir.Block,
    ret: ir.SSAValue | Sequence[ir.SSAValue] | None,
    output: types.TypeAttribute,
    *,
    inputs: tuple[types.TypeAttribute, ...] = (),
    name: str = "prog",
) -> ir.Method:
    """End `block` with a return and wrap it in a jeff method.

    `ret` is None, one value, or a sequence of values.
    """
    if ret is None:
        values: tuple[ir.SSAValue, ...] = ()
    elif isinstance(ret, ir.SSAValue):
        values = (ret,)
    else:
        values = tuple(ret)
    block.stmts.append(stmts.Return(*values))
    code = func.Function(
        sym_name=name,
        body=ir.Region(block),
        signature=func.Signature(inputs=tuple(inputs), output=output),
    )
    return ir.Method(dialects=kernel, code=code, sym_name=name)


def _body(inputs: Sequence[ir.SSAValue], fill: Callable, *lead) -> ir.Block:
    block = ir.Block()
    lead_args = [block.args.append_from(t, n) for t, n in lead]
    in_args = [block.args.append_from(v.type, "in") for v in inputs]
    block.stmts.append(stmts.Yield(*fill(block, *lead_args, *in_args)))
    return block


def for_loop(
    block: ir.Block,
    start: ir.SSAValue,
    stop: ir.SSAValue,
    step: ir.SSAValue,
    state: Sequence[ir.SSAValue],
    fill: Callable,
) -> stmts.For:
    """Build a counted loop.

    `fill(body, index, *state_args)` returns the next state.
    The next state holds one value for each carried state value.
    """
    body = _body(state, fill, (types.Int, "i"))
    return add(block, stmts.For(start, stop, step, tuple(state), ir.Region(body)))


def switch(
    block: ir.Block,
    selector: ir.SSAValue,
    inputs: Sequence[ir.SSAValue],
    cases: list[Callable],
    default: Callable,
) -> stmts.Switch:
    """Build a branch on an integer selector.

    `cases[i](body, *inputs)` fills the region for selector value `i`.
    `default` fills the region for every selector value outside the cases.
    Each callable returns the values that its branch yields.
    """
    branches = [ir.Region(_body(inputs, case)) for case in cases]
    default_region = ir.Region(_body(inputs, default))
    return add(block, stmts.Switch(selector, tuple(inputs), branches, default_region))


def while_loop(
    block: ir.Block,
    inputs: Sequence[ir.SSAValue],
    before: Callable,
    after: Callable,
) -> stmts.While:
    """Build a while loop with a before region and an after region.

    `before(body, *inputs)` returns `(condition, *outputs)`.
    `after(body, *outputs)` returns the next inputs.
    """
    before_block = _body(inputs, before)
    yielded = before_block.last_stmt
    assert isinstance(yielded, stmts.Yield)
    after_block = _body(yielded.values[1:], after)
    return add(
        block,
        stmts.While(tuple(inputs), ir.Region(before_block), ir.Region(after_block)),
    )
