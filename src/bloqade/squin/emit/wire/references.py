"""Resolve qubit references in aliases, containers, lengths and indexing."""

from kirin import ir, types, interp
from kirin.dialects import py, func, ilist
from kirin.dialects.py import len as py_len, slice as py_slice

from bloqade.types import is_subtype, holds_qubits
from bloqade.constants import constant_int
from bloqade.analysis.indices import IndexExpr
from bloqade.squin.wire.errors import WireConversionError

from .base import EmitWire, WireFrame
from .values import (
    View,
    Value,
    Location,
    Register,
    select,
    known_items,
    select_slice,
    contains_location,
)


@py.assign.dialect.register(key="emit.squin_wire")
class Aliases(interp.MethodTable):
    """Resolve source aliases from their previously emitted operands."""

    @interp.impl(py.assign.Alias)
    def alias(
        self, emit: EmitWire, frame: WireFrame, stmt: py.assign.Alias
    ) -> tuple[Value]:
        """Retain the source value's emitted value or quantum location."""
        return (frame.get(stmt.value),)


@ilist.dialect.register(key="emit.squin_wire")
class Lists(interp.MethodTable):
    """Retain quantum lists as location sequences and emit classical lists."""

    @interp.impl(ilist.New)
    def new(
        self, emit: EmitWire, frame: WireFrame, stmt: ilist.New
    ) -> tuple[Value, ...]:
        """Build a source container or copy a classical list into the output."""
        values = frame.get_values(stmt.values)
        if holds_qubits(stmt.result.type) or any(
            contains_location(value) for value in values
        ):
            return (values,)
        return emit.eval_fallback(frame, stmt)


@py.tuple.dialect.register(key="emit.squin_wire")
class Tuples(interp.MethodTable):
    """Keep source tuple fields available for indexing and function returns."""

    @interp.impl(py.tuple.New)
    def new(self, emit: EmitWire, frame: WireFrame, stmt: py.tuple.New) -> tuple[Value]:
        """Record tuple fields without emitting a redundant source container."""
        return (frame.get_values(stmt.args),)


@py.binop.dialect.register(key="emit.squin_wire")
class Arithmetic(interp.MethodTable):
    """Resolve quantum list concatenation and emit ordinary arithmetic."""

    @interp.impl(py.Add)
    def add(self, emit: EmitWire, frame: WireFrame, stmt: py.Add) -> tuple[Value, ...]:
        """Concatenate known quantum sequences or copy the classical addition."""
        left, right = frame.get_values(stmt.args)
        if contains_location(left) or contains_location(right):
            a, b = known_items(left, stmt), known_items(right, stmt)
            if a is None or b is None:
                raise WireConversionError(
                    "Quantum concatenation requires known source lengths.", stmt
                )
            return (a + b,)
        return emit.eval_fallback(frame, stmt)


@py_len.dialect.register(key="emit.squin_wire")
class Lengths(interp.MethodTable):
    """Emit the length of a source sequence."""

    @interp.impl(py_len.Len)
    def length(
        self, emit: EmitWire, frame: WireFrame, stmt: py_len.Len
    ) -> tuple[Value]:
        """Read the source sequence's known or runtime length.

        A constant length also goes into `EmitWire.lengths`, so that a later index
        such as `qs[2:len(qs)]` reads it as a constant.
        """
        value = frame.get(stmt.value)
        size = len(value) if isinstance(value, tuple) else None
        if isinstance(value, (Register, View)) and value.length is not None:
            size = value.length.constant
        if size is not None:
            emit.lengths[stmt.result] = IndexExpr(size)
        else:
            emit.lengths.pop(stmt.result, None)
        return (emit.length_value(frame, value),)


@py.indexing.dialect.register(key="emit.squin_wire")
class Indexing(interp.MethodTable):
    """Select source quantum locations and emit ordinary classical indexing."""

    @interp.impl(py.GetItem)
    def getitem(
        self, emit: EmitWire, frame: WireFrame, stmt: py.GetItem
    ) -> tuple[Value, ...]:
        """Return the meaning of one source element or slice."""
        container, index_meaning = frame.get_values(stmt.args)
        index = emit.classical_value(frame, index_meaning)
        if isinstance(container, ir.SSAValue):
            return emit.eval_fallback(frame, stmt)
        if is_subtype(index.type, types.Slice):
            return (slice_item(emit, container, stmt),)
        return (element_item(emit, frame, container, index, stmt),)


UNRESOLVED_ITEM = (
    "A quantum container requires a tuple read at a constant index"
    " or a resolved register element."
)
"""Hold the error message for an index that names no known item of a container."""


def slice_item(emit: EmitWire, container: Value, stmt: py.GetItem) -> Value:
    """Return the meaning of `container[index]` for a source slice `index`."""
    start, stop, step = slice_bounds(emit, stmt.index, stmt)
    if isinstance(container, Location):
        return select_slice(container, start, stop, step, stmt)
    if isinstance(container, tuple) and all(
        bound is None or bound.constant is not None for bound in (start, stop)
    ):
        first = None if start is None else start.constant
        last = None if stop is None else stop.constant
        return container[first:last:step]
    raise WireConversionError(UNRESOLVED_ITEM, stmt)


def element_item(
    emit: EmitWire,
    frame: WireFrame,
    container: Value,
    index: ir.SSAValue,
    stmt: py.GetItem,
) -> Value:
    """Return the meaning of `container[index]` for the emitted integer `index`.

    A runtime index must already be a valid wire index, between 0 and the length minus
    1. Only a negative constant index counts from the end.
    """
    position = emit.index(stmt.index)
    if isinstance(container, Location):
        return select(container, position, stmt)
    if isinstance(container, tuple):
        item = position.constant
        if item is not None and -len(container) <= item < len(container):
            return container[item]
        if not contains_location(container):
            packed = emit.classical_value(frame, container)
            return frame.push(py.GetItem(packed, index)).results[0]
    raise WireConversionError(UNRESOLVED_ITEM, stmt)


def slice_bounds(
    emit: EmitWire, value: ir.SSAValue, at: ir.Statement
) -> tuple[IndexExpr | None, IndexExpr | None, int]:
    """Read the bounds of the source slice `value` as index expressions."""
    node = value.owner
    if isinstance(node, py_slice.Slice):
        start = None if is_none(node.start) else emit.index(node.start)
        stop = None if is_none(node.stop) else emit.index(node.stop)
        step = 1 if is_none(node.step) else constant_int(node.step)
    elif isinstance(node, py.Constant) and isinstance(
        sliced := node.value.unwrap(), slice
    ):
        start = None if sliced.start is None else IndexExpr(sliced.start)
        stop = None if sliced.stop is None else IndexExpr(sliced.stop)
        step = 1 if sliced.step is None else sliced.step
    else:
        raise WireConversionError("The slice bounds have no supported source form.", at)
    if step is None or step == 0:
        raise WireConversionError(
            "A quantum slice requires a nonzero constant step.", at
        )
    return start, stop, step


def is_none(value: ir.SSAValue) -> bool:
    """Check whether `value` is the constant `None`.

    The check reads the constant itself first. A kernel without constant folding
    gives its constants the type `Bottom`, and `Bottom` passes every subtype test.
    """
    owner = value.owner
    if isinstance(owner, func.ConstantNone):
        return True
    if isinstance(owner, py.Constant):
        return owner.value.unwrap() is None
    typ = value.type
    return is_subtype(typ, types.NoneType)
