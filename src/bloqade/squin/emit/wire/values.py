"""Describe source qubit references as immutable locations in emitted allocations.

The items of a `Register` or a `View` are qubits if its `row_shape` is empty.
Otherwise its items are the rows of a nested register, and the flat register holds
the rows in order. For example, `IList[IList[Qubit, 2], 3]` is a `Register` of 3
items with the row shape `(2,)`.
"""

from __future__ import annotations

import math
from typing import TypeAlias
from dataclasses import dataclass

from kirin import ir
from kirin.dialects import py, ilist

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
    """Name one whole register allocation."""

    root: ir.SSAValue
    length: IndexExpr | None = None
    """Hold the number of items, or None if it is unknown."""
    row_shape: tuple[int | None, ...] = ()
    """Hold the dimensions of one item row, outermost first, or `()` for qubit items."""


@dataclass(frozen=True)
class View:
    """Name the items of a register at the flat indices of `span`."""

    root: ir.SSAValue
    span: Slice
    """Hold the flat index where each item starts."""
    row_shape: tuple[int | None, ...] = ()
    """Hold the dimensions of one item row, outermost first, or `()` for qubit items."""

    @property
    def length(self) -> IndexExpr | None:
        """Return the number of items, or None if it is unknown."""
        return self.span.length


Single: TypeAlias = Qubit | Element
"""Name a location of exactly one qubit."""

Part: TypeAlias = Register | View
"""Name a location that holds indexed items."""

Location: TypeAlias = Single | Part
"""Name the allocation, the qubit or the register part that a source reference holds."""


@dataclass(frozen=True)
class WrapperSelf:
    """Name the self argument of a library wrapper, which has no emitted form."""


Value: TypeAlias = ir.SSAValue | Location | WrapperSelf | tuple["Value", ...] | None
"""Represent an emitted classical value, a quantum location, or a source container.

None is the result of a statement without results, which Kirin's emitter gives.
"""


def singles(items: tuple[Value, ...], at: ir.Statement) -> tuple[Single, ...]:
    """Return `items`, which must all be qubit locations of known places."""
    qubits = tuple(item for item in items if isinstance(item, (Qubit, Element)))
    if len(qubits) != len(items):
        raise WireConversionError(
            f"A qubit of '{at.name}' has no place in a known allocation.", at
        )
    return qubits


def contains_location(value: Value) -> bool:
    """Check whether `value` is a location or a tuple that holds a location."""
    return isinstance(value, (Qubit, Element, Register, View)) or (
        isinstance(value, tuple) and any(contains_location(item) for item in value)
    )


def items_of(location: Location, at: ir.Statement) -> Part:
    """Return `location` if it holds indexed items, or raise an error for one qubit."""
    if not isinstance(location, (Register, View)):
        raise WireConversionError("A scalar qubit has no indexed elements.", at)
    return location


def select(location: Location, index: IndexExpr, at: ir.Statement) -> Location:
    """Return the location of item `index` of a register or a register part."""
    part = items_of(location, at)
    index = checked_index(part.length, index, at)
    match part:
        case Register(root, _, ()):
            return Element(root, index)
        case View(root, span, ()):
            return Element(root, span.item(index))
        case Register(root, _, row_shape):
            return row(root, index.scale(row_width(row_shape, at)), row_shape, at)
        case View(root, span, row_shape):
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
                "A negative index needs a register of known length.",
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


def known_shape(shape: tuple[int | None, ...], at: ir.Statement) -> tuple[int, ...]:
    """Return the row dimensions `shape`, which must all be known."""
    known = tuple(size for size in shape if size is not None)
    if len(known) != len(shape):
        raise WireConversionError(
            "Nested register indexing requires known inner dimensions.", at
        )
    return known


def row_width(shape: tuple[int | None, ...], at: ir.Statement) -> int:
    """Return the number of qubits in one row of the dimensions `shape`."""
    return math.prod(known_shape(shape, at))


def row(
    root: ir.SSAValue, start: IndexExpr, shape: tuple[int | None, ...], at: ir.Statement
) -> View:
    """Return the location of the row of dimensions `shape` that starts at `start`."""
    outer, *inner = known_shape(shape, at)
    return View(root, Slice(start, math.prod(inner), IndexExpr(outer)), tuple(inner))


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
    if part.row_shape:
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


def known_items(value: Value, at: ir.Statement) -> tuple[Value, ...] | None:
    """Return the item meanings of a container whose length is known, or None.

    A constant empty list, such as the operand of `broadcast.x([])`, has no items.
    """
    if isinstance(value, tuple):
        return value
    if (
        isinstance(value, ir.SSAValue)
        and isinstance(value.owner, ilist.New)
        and not value.owner.values
    ):
        return ()
    if isinstance(value, ir.SSAValue) and isinstance(value.owner, py.Constant):
        data = value.owner.value.unwrap()
        if isinstance(data, ilist.IList) and len(data) == 0:
            return ()
    if isinstance(value, (Register, View)) and value.length is not None:
        if (count := value.length.constant) is not None:
            return tuple(select(value, IndexExpr(i), at) for i in range(max(0, count)))
    return None


def extent(location: Location) -> tuple[IndexExpr, IndexExpr] | None:
    """Return the first flat index and the qubit count of a contiguous location.

    The result is None for a location whose qubits the emitter cannot bound, such as
    a whole register.
    """
    match location:
        case Element(_, index):
            return index, IndexExpr(1)
        case View(_, Slice(start, 1, length), ()) if length is not None:
            return start, length
    return None


def apart(left: Location, right: Location) -> bool:
    """Check whether two locations provably share no qubit.

    Locations with different roots name different allocations. 2 contiguous locations
    of one register are apart if one ends before the other starts.
    """
    if left.root is not right.root:
        return True
    a, b = extent(left), extent(right)
    if a is None or b is None:
        return False
    (a_start, a_count), (b_start, b_count) = a, b
    gaps = (
        (a_start + a_count - b_start).constant,
        (b_start + b_count - a_start).constant,
    )
    return any(gap is not None and gap <= 0 for gap in gaps)
