"""Run bounded rewrites, insert replacement statements, and reject recursion.

`put` and `replace` are the 2 steps that every rewrite rule of the wire
conversions uses to swap a statement for its replacement. `pack`, `set_signature`
and `Retype` build the function boundaries of all conversions.
"""

from typing import TypeVar
from dataclasses import field, dataclass
from collections.abc import Callable, Iterable, Sequence

from kirin import ir, types
from kirin.rewrite import Walk, Fixpoint
from kirin.dialects import py, func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin.wire.errors import WireConversionError

StatementT = TypeVar("StatementT", bound=ir.Statement)


def put(stmt: StatementT, before: ir.Statement) -> StatementT:
    """Insert `stmt` before the statement `before` and return `stmt`."""
    stmt.insert_before(before)
    return stmt


def replace(node: ir.Statement, *values: ir.SSAValue) -> None:
    """Replace each result of `node` with the value at its position and delete `node`."""
    for result, value in zip(node.results, values, strict=True):
        result.replace_by(value)
    node.delete()


def pack(values: Sequence[ir.SSAValue], before: ir.Statement) -> ir.SSAValue:
    """Return `None`, the single value or a tuple of `values`, inserted before `before`."""
    if not values:
        return put(func.ConstantNone(), before).result
    if len(values) == 1:
        return values[0]
    return put(py.tuple.New(tuple(values)), before).result


def unpack(
    value: ir.SSAValue, outputs: Sequence[types.TypeAttribute], before: ir.Statement
) -> tuple[ir.SSAValue, ...]:
    """Return field `k` of the tuple `value` with the type `outputs[k]` for each `k`.

    The reads go before `before`. This is the inverse of `pack` for 2 or more values.
    """
    fields: list[ir.SSAValue] = []
    for k, typ in enumerate(outputs):
        index = put(py.Constant(k), before).result
        item = put(py.GetItem(value, index), before)
        item.result.type = typ
        fields.append(item.result)
    return tuple(fields)


def set_signature(
    function: func.Function,
    inputs: tuple[types.TypeAttribute, ...],
    output: types.TypeAttribute,
) -> None:
    """Give `function` the signature of `inputs` and `output`, and its self argument."""
    function.signature = func.Signature(inputs=inputs, output=output)
    function.body.blocks[0].args[0].type = types.MethodType[list(inputs), output]


@dataclass
class Retype(RewriteRule):
    """Give each block argument, result and function signature the type of `convert`."""

    convert: Callable[[types.TypeAttribute], types.TypeAttribute]

    def rewrite_Block(self, node: ir.Block) -> RewriteResult:
        """Convert the type of each block argument."""
        return self.retype(node.args)

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Convert the type of each result and the signature of a function."""
        result = self.retype(node.results)
        if isinstance(node, func.Function):
            signature = node.signature
            inputs = tuple(self.convert(typ) for typ in signature.inputs)
            output = self.convert(signature.output)
            if (inputs, output) != (signature.inputs, signature.output):
                set_signature(node, inputs, output)
                result = RewriteResult(has_done_something=True)
        return result

    def retype(self, values: Iterable[ir.SSAValue]) -> RewriteResult:
        """Convert the type of each value of `values`."""
        changed = False
        for value in values:
            typ = self.convert(value.type)
            changed |= typ != value.type
            value.type = typ
        return RewriteResult(has_done_something=changed)


@dataclass
class CheckedFixpoint(Fixpoint):
    """Report exhaustion of Kirin's rewrite limit as a conversion failure."""

    def rewrite(self, node: ir.IRNode) -> RewriteResult:
        """Run the rules until convergence or report the configured iteration limit."""
        result = super().rewrite(node)
        if result.exceeded_max_iter:
            raise WireConversionError(
                f"Wire rewriting did not converge within {self.max_iter} iterations.",
                node,
            )
        return result


def invoked(node: ir.Statement) -> ir.Method | None:
    """Return the callee of a `func.Invoke`, or None for any other statement."""
    return node.callee if isinstance(node, func.Invoke) else None


@dataclass
class Calls(RewriteRule):
    """Collect static callees through Kirin's walker."""

    callee_of: Callable[[ir.Statement], ir.Method | None] = invoked
    """Return the static callee of a call statement, or None for any other one."""
    callees: dict[ir.Method, None] = field(default_factory=dict)

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Record each direct call without changing its statement."""
        if (callee := self.callee_of(node)) is not None:
            self.callees[callee] = None
        return RewriteResult()


def reachable(
    method: ir.Method,
    skip: Callable[[ir.Method], bool] = lambda _: False,
    callee_of: Callable[[ir.Statement], ir.Method | None] = invoked,
) -> list[ir.Method]:
    """Return the reachable methods, callees first, and reject call cycles.

    `callee_of` names the callee of a call statement, such as a Jeff `Call`.
    """
    done: dict[ir.Method, None] = {}
    active: set[ir.Method] = set()

    def visit(current: ir.Method) -> None:
        if current in active:
            raise WireConversionError(
                f"Wire conversion does not support recursive calls to '{current.sym_name}'.",
                current.code,
            )
        if current in done or skip(current):
            return
        active.add(current)
        calls = Calls(callee_of)
        Walk(calls).rewrite(current.code)
        for callee in calls.callees:
            visit(callee)
        active.remove(current)
        done[current] = None

    visit(method)
    return list(done)
