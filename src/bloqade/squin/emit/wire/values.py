"""Describe source qubit references as immutable locations in emitted allocations.

The items of a `Register` or a `View` are qubits. The items of a `Grid` or `Rows`
are the rows of a nested register, whose flat root holds the rows in order.
"""

from __future__ import annotations

import math
from typing import TypeAlias
from dataclasses import dataclass

from kirin import ir

from bloqade.analysis.indices import Slice, IndexExpr, python_slice
from bloqade.squin.wire.errors import WireConversionError


@dataclass(frozen=True)
class Qubit:
    """Name one standalone qubit allocation."""

    root: ir.SSAValue


@dataclass(frozen=True)
class Element:
    """Name the qubit of a register at a flat root index."""

    root: ir.SSAValue
    index: IndexExpr


@dataclass(frozen=True)
class Register:
    """Name one whole flat register allocation."""

    root: ir.SSAValue
    length: IndexExpr | None = None
    """The number of qubits, or None if it is unknown."""


@dataclass(frozen=True)
class View:
    """Name a contiguous slice of the qubits of a register."""

    root: ir.SSAValue
    span: Slice
    """The flat root index of each qubit of the slice."""

    @property
    def length(self) -> IndexExpr | None:
        """Return the number of qubits, or None if it is unknown."""
        return self.span.length


@dataclass(frozen=True)
class Grid:
    """Name one whole nested register allocation."""

    root: ir.SSAValue
    length: IndexExpr | None
    """The number of rows, or None if it is unknown."""
    row_shape: tuple[int | None, ...]
    """The dimensions of one row, outermost first."""


@dataclass(frozen=True)
class Rows:
    """Name a row of a nested register whose items are rows themselves."""

    root: ir.SSAValue
    span: Slice
    """The flat root index where each item row starts."""
    row_shape: tuple[int, ...]
    """The dimensions of one item row, outermost first."""

    @property
    def length(self) -> IndexExpr | None:
        """Return the number of item rows."""
        return self.span.length


Location: TypeAlias = Qubit | Element | Register | View | Grid | Rows
"""Name the allocation, the qubit or the register part that a source reference holds."""

Part: TypeAlias = Register | View | Grid | Rows
"""Name a location that holds indexed items."""

Value: TypeAlias = ir.SSAValue | Location | tuple["Value", ...] | None
"""Represent an emitted classical value, a quantum location, or a source container.

None is the meaning of the self argument of a library wrapper, which has no
emitted form.
"""


def is_qubit(value: Value) -> bool:
    """Check whether `value` names exactly one qubit."""
    return isinstance(value, (Qubit, Element))


def contains_location(value: Value) -> bool:
    """Identify source containers that still contain quantum locations."""
    return isinstance(value, (Qubit, Element, Register, View, Grid, Rows)) or (
        isinstance(value, tuple) and any(contains_location(item) for item in value)
    )


def items_of(location: Location, at: ir.Statement) -> Part:
    """Return `location` if it holds indexed items, or raise an error for one qubit."""
    if not isinstance(location, (Register, View, Grid, Rows)):
        raise WireConversionError("A scalar qubit has no indexed elements.", at)
    return location


def select(location: Location, index: IndexExpr, at: ir.Statement) -> Location:
    """Return the location of item `index` of a register or a register part."""
    part = items_of(location, at)
    index = checked_index(part.length, index, at)
    match part:
        case Register(root):
            return Element(root, index)
        case View(root, span):
            return Element(root, span.item(index))
        case Grid(root, _, row_shape):
            return row(root, index.scale(row_width(row_shape, at)), row_shape, at)
        case Rows(root, span, row_shape):
            return row(root, span.item(index), row_shape, at)


def checked_index(
    length: IndexExpr | None, index: IndexExpr, at: ir.Statement
) -> IndexExpr:
    """Count a negative constant index from the end and check the index bounds.

    The check rejects an index that lies outside the length in any execution.
    """
    count = None if length is None else length.constant
    position = index.constant
    if position is not None and position < 0:
        if count is None:
            raise WireConversionError(
                "Cannot resolve a negative index into a register of unknown length.",
                at,
            )
        position += count
        index = IndexExpr(position)
    if count is not None and position is not None and not 0 <= position < count:
        raise WireConversionError(
            "The register index has no place in this allocation.", at
        )
    lowest = index.bounds()
    gap = None if length is None else (length - index).bounds()
    if (lowest is not None and lowest[0] < 0) or (gap is not None and gap[0] <= 0):
        raise WireConversionError(
            "The register index can lie outside this allocation.", at
        )
    return index


def known_shape(
    shape: tuple[int | None, ...], at: ir.Statement | None
) -> tuple[int, ...]:
    """Return the row dimensions `shape`, which must all be known."""
    known = tuple(size for size in shape if size is not None)
    if len(known) != len(shape):
        raise WireConversionError(
            "Nested register indexing requires known inner dimensions.", at
        )
    return known


def row_width(shape: tuple[int | None, ...], at: ir.Statement | None) -> int:
    """Return the number of qubits in one row of the dimensions `shape`."""
    return math.prod(known_shape(shape, at))


def row(
    root: ir.SSAValue, start: IndexExpr, shape: tuple[int | None, ...], at: ir.Statement
) -> View | Rows:
    """Return the location of the row of dimensions `shape` that starts at `start`."""
    outer, *inner = known_shape(shape, at)
    if not inner:
        return View(root, Slice(start, 1, IndexExpr(outer)))
    return Rows(root, Slice(start, math.prod(inner), IndexExpr(outer)), tuple(inner))


def select_slice(
    location: Location,
    start: IndexExpr | None,
    stop: IndexExpr | None,
    step: int,
    at: ir.Statement,
) -> Value:
    """Return the meaning of a register or a register part sliced with `start:stop:step`.

    A slice of qubits gives one `View`. A slice of rows gives a tuple of rows.
    """
    part = items_of(location, at)
    count = None if part.length is None else part.length.constant
    if isinstance(part, (Grid, Rows)):
        if count is None or any(
            x is not None and x.constant is None for x in (start, stop)
        ):
            raise WireConversionError(
                "A nested register slice requires constant bounds and an outer length.",
                at,
            )
        selected = range(count)[
            slice(
                None if start is None else start.constant,
                None if stop is None else stop.constant,
                step,
            )
        ]
        return tuple(select(part, IndexExpr(i), at) for i in selected)
    span = python_slice(start, stop, step, count)
    if span is not None and isinstance(part, View):
        span = part.span.then(span)
    if span is None:
        raise WireConversionError("The slice has no place in a known allocation.", at)
    return View(part.root, span)
