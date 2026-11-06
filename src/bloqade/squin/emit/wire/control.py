"""Emit structured regions once with explicit incoming and outgoing wire values.

A loop or a branch carries the latest wire of every root of the enclosing frame. A body
yields its classical results and then those wires in the same order.
"""

from collections.abc import Sequence

from kirin import ir, types, interp
from kirin.dialects import py, scf, ssacfg

from bloqade.squin.wire.errors import WireConversionError

from .base import EmitWire, WireFrame, body_of
from .values import Value, contains_location


def carry_wires(frame: WireFrame, body: WireFrame) -> tuple[ir.SSAValue, ...]:
    """Add one block argument to `body` for the latest value of each root of `frame`.

    The result holds the allocation roots in block argument order.
    """
    roots = tuple(frame.latest)
    body.latest = {
        root: body.output.args.append_from(frame.latest[root].type) for root in roots
    }
    return roots


def yield_wires(
    body: WireFrame, roots: Sequence[ir.SSAValue], classical: Sequence[ir.SSAValue]
) -> None:
    """Free the body's local allocations and yield its classical results and wires."""
    body.free_local_allocations()
    body.push(scf.Yield(*classical, *(body.latest[root] for root in roots)))


def same_locations(
    left: Sequence[Value], right: Sequence[Value], stmt: ir.Statement, message: str
) -> None:
    """Raise `message` unless both sequences hold the same location at each position.

    A loop body must yield each carried location back, and both branches must yield
    the same location at each position.
    """
    for a, b in zip(left, right, strict=True):
        if (contains_location(a) or contains_location(b)) and a != b:
            raise WireConversionError(message, stmt)


def resume(
    frame: WireFrame,
    made: ir.Statement,
    roots: Sequence[ir.SSAValue],
    values: Sequence[Value],
    classical_indices: Sequence[int],
) -> tuple[Value, ...]:
    """Continue `frame` after the loop or branch `made` and return its source results.

    The results of `made` hold one classical value for each entry of
    `classical_indices` and then the next wire of each root. The returned source
    results equal `values` with those classical entries replaced.
    """
    count = len(classical_indices)
    frame.latest.update(zip(roots, made.results[count:], strict=True))
    results = list(values)
    for i, value in zip(classical_indices, made.results[:count], strict=True):
        results[i] = value
    return tuple(results)


@ssacfg.dialect.register(key="emit.squin_wire")
class Regions(ssacfg.Concrete):
    """Use Kirin's region interpreter to visit each source statement in order."""


@py.boolop.dialect.register(key="emit.squin_wire")
class BooleanOperands(interp.MethodTable):
    """Preserve the operand values that Python's boolean operators return."""

    @interp.impl(py.boolop.And)
    @interp.impl(py.boolop.Or)
    def select(
        self, emit: EmitWire, frame: WireFrame, stmt: py.boolop.And | py.boolop.Or
    ) -> tuple[ir.SSAValue]:
        """Select an operand before type inference determines the result type.

        Kirin declares boolean operator results as bool, even when execution returns
        a numeric operand. Both operands already exist when this handler runs.
        """
        lhs, rhs = (
            emit.classical_value(frame, value) for value in frame.get_values(stmt.args)
        )
        if all(isinstance(use.stmt, py.Not) for use in stmt.result.uses):
            # A consumer that applies `not` needs only the operand's truth value.
            bits = tuple(
                frame.push(py.Not(frame.push(py.Not(value)).result)).result
                for value in (lhs, rhs)
            )
            return (frame.push(type(stmt)(*bits)).result,)
        condition = frame.push(py.Not(lhs)).result
        yes, no = (lhs, rhs) if isinstance(stmt, py.boolop.And) else (rhs, lhs)
        branches = [
            ir.Block([scf.Yield(value)], argtypes=(types.Bool,)) for value in (yes, no)
        ]
        return (frame.push(scf.IfElse(condition, *branches)).results[0],)


@scf.dialect.register(key="emit.squin_wire")
class ControlFlow(interp.MethodTable):
    """Construct loop and branch bodies, each with its own `latest` map."""

    @interp.impl(scf.Yield)
    def yield_(
        self, emit: EmitWire, frame: WireFrame, stmt: scf.Yield
    ) -> interp.YieldValue[Value]:
        """Return source meanings to the region handler that constructs the output yield."""
        return interp.YieldValue(frame.get_values(stmt.values))

    @interp.impl(scf.For)
    def loop(
        self, emit: EmitWire, frame: WireFrame, stmt: scf.For
    ) -> tuple[Value, ...]:
        """Convert the body once and carry all available outer wires through the loop."""
        initial = frame.get_values(stmt.initializers)
        classical_indices = tuple(
            i for i, value in enumerate(initial) if not contains_location(value)
        )
        classical = tuple(
            emit.classical_value(frame, initial[i]) for i in classical_indices
        )
        if contains_location(frame.get(stmt.iterable)):
            raise WireConversionError(
                "A loop cannot iterate over qubits. Iterate over `range(len(qs))`"
                " and index the qubits.",
                stmt,
            )
        iterable = emit.classical_value(frame, frame.get(stmt.iterable))
        source_args = body_of(stmt.body, stmt, len(stmt.initializers) + 1).args
        with emit.new_frame(stmt, has_parent_access=True) as body:
            body.site, body.current_stmt = frame.site, stmt
            arguments = list(initial)
            index = body.output.args.append_from(
                source_args[0].type, source_args[0].name
            )
            for i, value in zip(classical_indices, classical, strict=True):
                arguments[i] = body.output.args.append_from(
                    value.type, source_args[i + 1].name
                )
            roots = carry_wires(frame, body)
            incoming = tuple(frame.latest[root] for root in roots)
            yielded = emit.frame_call_region(body, stmt, stmt.body, index, *arguments)
            if not isinstance(yielded, tuple) or len(yielded) != len(initial):
                raise WireConversionError(
                    "A loop must yield its source state in initializer order.", stmt
                )
            # A quantum initializer gets no block argument, because `carry_wires`
            # carries its root. The body must yield the same location back.
            same_locations(
                initial,
                yielded,
                stmt,
                "A loop must yield each qubit reference that it carries in its"
                " position.",
            )
            outputs = tuple(
                emit.classical_value(body, yielded[i]) for i in classical_indices
            )
            yield_wires(body, roots, outputs)
        # `scf.For` reads its result types from the final yield of the body.
        made = scf.For(iterable, ir.Region(body.output), *classical, *incoming)
        made.attributes.update(stmt.attributes)
        frame.push(made)
        return resume(frame, made, roots, initial, classical_indices)

    @interp.impl(scf.IfElse)
    def branch(
        self, emit: EmitWire, frame: WireFrame, stmt: scf.IfElse
    ) -> tuple[Value, ...]:
        """Convert both paths from the same incoming state and join their explicit wire results."""
        condition = emit.classical_value(frame, frame.get(stmt.cond))
        roots = tuple(frame.latest)
        bodies: list[WireFrame] = []
        yields: list[tuple[Value, ...]] = []
        for region in (stmt.then_body, stmt.else_body):
            with emit.new_frame(stmt, has_parent_access=True) as body:
                body.site, body.current_stmt = frame.site, stmt
                # Each body of Kirin's `scf.IfElse` gets the condition as a block
                # argument.
                arguments = tuple(
                    body.output.args.append_from(arg.type, arg.name)
                    for arg in body_of(region, stmt, 1).args
                )
                body.latest = dict(frame.latest)
                yielded = emit.frame_call_region(body, stmt, region, *arguments)
                if not isinstance(yielded, tuple):
                    raise WireConversionError("A branch must end with a yield.", stmt)
                bodies.append(body)
                yields.append(yielded)
        left, right = yields
        if len(left) != len(right):
            raise WireConversionError("Branch results must have matching counts.", stmt)
        same_locations(
            left,
            right,
            stmt,
            "Both branches must give the same qubit reference at each result.",
        )
        classical_indices = [
            i for i, value in enumerate(left) if not contains_location(value)
        ]
        for body, yielded in zip(bodies, yields, strict=True):
            outputs = tuple(
                emit.classical_value(body, yielded[i]) for i in classical_indices
            )
            yield_wires(body, roots, outputs)
        made = scf.IfElse(
            condition, ir.Region(bodies[0].output), ir.Region(bodies[1].output)
        )
        made.attributes.update(stmt.attributes)
        frame.push(made)
        return resume(frame, made, roots, left, classical_indices)
