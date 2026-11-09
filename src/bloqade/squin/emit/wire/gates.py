"""Emit qubit allocations, scalar wire operations on qubits and register operations on registers or slices."""

from itertools import combinations

from kirin import ir, types, interp
from kirin.dialects import ilist
from kirin.interp.table import Def

from bloqade import qubit
from bloqade.types import item_type
from bloqade.squin.gate import stmts as gate_stmts
from bloqade.squin.wire import stmts
from bloqade.squin.noise import stmts as noise_stmts
from bloqade.analysis.indices import Slice
from bloqade.squin.wire.stmts import Operation
from bloqade.native.dialects.gate import stmts as native_stmts
from bloqade.squin.rewrite.wire.sources import ENTRIES, Entry

from .base import EmitWire, WireFrame
from .values import (
    View,
    Value,
    Single,
    Location,
    Register,
    apart,
    singles,
    known_items,
)
from .correlated import emit_correlated


def apply(
    emit: EmitWire,
    frame: WireFrame,
    stmt: ir.Statement,
    entry: Entry,
    locations: tuple[Location, ...],
    register: bool,
) -> Operation:
    """Emit the wire form of `stmt` on the operands at `locations` and restore them.

    If `register` is True, each location is a register part and the statement acts on
    whole registers. Otherwise each location is one qubit.
    """
    build = entry.register if register else entry.scalar

    def made(inputs: tuple[ir.SSAValue, ...]) -> Operation:
        params = tuple(
            emit.classical_value(frame, frame.get(value))
            for value in entry.param_operands(stmt)
        )
        return build(inputs, params, entry.adjoint(stmt))

    operation = emit.operate(frame, locations, made)
    assert isinstance(operation, Operation)
    return operation


def register_parts(operands: tuple[Value, ...]) -> tuple[Register | View, ...] | None:
    """Return the operands if each one is a whole register or a step-1 slice of qubits."""
    parts: list[Register | View] = []
    for value in operands:
        match value:
            case Register(row_shape=()) | View(span=Slice(step=1), row_shape=()):
                parts.append(value)
            case _:
                return None
    return tuple(parts)


def register_gate(
    emit: EmitWire,
    frame: WireFrame,
    stmt: ir.Statement,
    entry: Entry,
    parts: tuple[Register | View, ...],
) -> tuple[ir.SSAValue, ...]:
    """Emit the register form of `stmt` and return its classical list results.

    Operands of different known lengths fail, unless the statement stops at the
    shortest register.
    """
    counts = [None if part.length is None else part.length.constant for part in parts]
    known = {count for count in counts if count is not None}
    if not entry.truncates and len(known) > 1:
        raise ir.ValidationError(
            stmt, f"'{stmt.name}' requires qubit lists of equal length."
        )
    if entry.truncates:
        size = None if None in counts else min(known)
    else:
        size = next(iter(known), None)
    made = apply(emit, frame, stmt, entry, parts, register=True)
    length = types.Any if size is None else types.Literal(size)
    for value in made.classical:
        value.type = ilist.IListType[item_type(value.type), length]
    return made.classical


def qubit_groups(
    entry: Entry, operands: tuple[Value, ...], stmt: ir.Statement
) -> list[tuple[Single, ...]]:
    """Group the qubits of the operands like Python's `zip`, one qubit per operand.

    Each operand must have a known length, and all qubits must have known places.
    """
    items = tuple(known_items(value, stmt) for value in operands)
    if any(item is None for item in items):
        if register_parts(operands) is not None:
            raise ir.ValidationError(
                stmt,
                "A runtime broadcast over register parts that can share qubits has"
                " no wire form.",
            )
        if not all(isinstance(value, (Register, View, tuple)) for value in operands):
            raise ir.ValidationError(
                stmt, "A runtime broadcast requires resolved register operands."
            )
        if any(isinstance(value, tuple) for value in operands):
            raise ir.ValidationError(
                stmt,
                "A runtime broadcast cannot mix a register of runtime length with a"
                " list of qubits.",
            )
        raise ir.ValidationError(
            stmt, "A runtime broadcast over a strided or nested slice has no wire form."
        )
    known = tuple(item for item in items if item is not None)
    if not entry.truncates and len({len(item) for item in known}) > 1:
        raise ir.ValidationError(
            stmt, f"'{stmt.name}' requires qubit lists of equal length."
        )
    return [singles(group, stmt) for group in zip(*known)]


def emit_gate(
    emit: EmitWire, frame: WireFrame, stmt: ir.Statement
) -> tuple[Value, ...]:
    """Emit the wire form of the squin statement `stmt` on registers or on qubits.

    Whole registers and step-1 slices that share no qubit get one register
    operation. Other operands group their qubits like Python's `zip`. Groups that
    share no qubit form one statement, and overlapping groups get one statement each.
    """
    entry = ENTRIES[type(stmt)]
    operands = tuple(frame.get(value) for value in entry.qubit_operands(stmt))
    parts = register_parts(operands)
    if parts is not None and all(apart(a, b) for a, b in combinations(parts, 2)):
        return register_gate(emit, frame, stmt, entry, parts)
    groups = qubit_groups(entry, operands, stmt)
    if (
        entry.broadcast
        and len(groups) > 1
        and all(
            apart(a, b)
            for left, right in combinations(groups, 2)
            for a in left
            for b in right
        )
    ):
        flat = tuple(location for group in groups for location in group)
        apply(emit, frame, stmt, entry, flat, register=False)
        return ()
    outputs: list[list[ir.SSAValue]] = [[] for _ in entry.results]
    for group in groups:
        made = apply(emit, frame, stmt, entry, group, register=False)
        for collected, value in zip(outputs, made.classical, strict=True):
            collected.append(value)
    return tuple(
        frame.push(ilist.New(tuple(values), elem_type=item_type(result.type))).result
        for result, values in zip(entry.result_values(stmt), outputs, strict=True)
    )


Rule = Def[
    interp.MethodTable, EmitWire, WireFrame, ir.Statement, interp.StatementResult[Value]
]
"""Name the type of a method of an emitter method table."""


def operation(
    self: interp.MethodTable, emit: EmitWire, frame: WireFrame, stmt: ir.Statement
) -> interp.StatementResult[Value]:
    """Emit the wire form of the squin statement `stmt`."""
    return emit_gate(emit, frame, stmt)


def every_source(dialect: ir.Dialect) -> Rule:
    """Return `operation` as the method of every statement of `dialect` in `ENTRIES`."""
    first, *rest = (op for op in ENTRIES if op.dialect is dialect)
    rule: Rule = interp.impl(first)(operation)
    for op in rest:
        rule = interp.impl(op)(rule)
    return rule


@gate_stmts.dialect.register(key="emit.squin_wire")
class Gates(interp.MethodTable):
    """Emit each squin gate with `emit_gate`."""

    gate = every_source(gate_stmts.dialect)


@noise_stmts.dialect.register(key="emit.squin_wire")
class Noises(interp.MethodTable):
    """Emit each squin noise channel on flat qubit lists with `emit_gate`."""

    noise = every_source(noise_stmts.dialect)

    @interp.impl(noise_stmts.CorrelatedQubitLoss)
    def correlated_loss(
        self, emit: EmitWire, frame: WireFrame, stmt: noise_stmts.CorrelatedQubitLoss
    ) -> tuple[()]:
        """Apply one shared loss event within each source group."""
        return emit_correlated(emit, frame, stmt)


@native_stmts.dialect.register(key="emit.squin_wire")
class NativeGates(interp.MethodTable):
    """Emit each native gate with `emit_gate`."""

    gate = every_source(native_stmts.dialect)


@qubit.dialect.register(key="emit.squin_wire")
class Qubits(interp.MethodTable):
    """Emit standalone qubit allocations, and each measurement and reset with `emit_gate`."""

    @interp.impl(qubit.stmts.New)
    def new(
        self, emit: EmitWire, frame: WireFrame, stmt: qubit.stmts.New
    ) -> tuple[Value]:
        """Create a qubit and record its lifetime in the current region."""
        return (emit.new_qubit(frame, frame.push(stmts.Alloc()).result),)

    operation = every_source(qubit.dialect)
