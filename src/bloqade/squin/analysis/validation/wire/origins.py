"""Represent wire origins and tuple fields in the position validation lattice.

A handle names an allocation by its root, which is an SSA value or, for a fresh call
result, a pair of the call and the callee root.
"""

from __future__ import annotations

from typing import TypeAlias
from dataclasses import replace, dataclass
from collections.abc import Hashable

from kirin import ir
from kirin.lattice import BoundedLattice

from bloqade.analysis.indices import IndexExpr
from bloqade.squin.wire.types import WireType


@dataclass(frozen=True)
class QubitHandle:
    """Identify one standalone qubit allocation."""

    root: Hashable
    """The identity of the allocation."""


@dataclass(frozen=True)
class RegisterHandle:
    """Identify one whole register allocation."""

    root: Hashable
    """The identity of the allocation."""
    length: IndexExpr | None = None
    """The number of elements of the register, or None if it is unknown."""


@dataclass(frozen=True)
class ElementHandle:
    """Identify one element of a register allocation."""

    root: Hashable
    """The identity of the register allocation."""
    index: IndexExpr
    """The index of the element in the register."""


@dataclass(frozen=True)
class SliceHandle:
    """Identify the range that a `TakeSlice` moved out of a register allocation."""

    root: Hashable
    """The identity of the register allocation."""
    start: IndexExpr
    """The index of the first element of the range in the register."""


Handle: TypeAlias = QubitHandle | RegisterHandle | ElementHandle | SliceHandle
"""Identify an allocation, one element of a register or a range of a register."""


def fresh_origin(value: ir.SSAValue, length: IndexExpr | None = None) -> Origin:
    """Return the origin of the new allocation that `value` names."""
    if value.type == WireType:
        return HandleOrigin(QubitHandle(value))
    return HandleOrigin(RegisterHandle(value, length))


def element_of(origin: Origin, index: IndexExpr) -> Origin:
    """Return the origin of element `index` of a register or slice origin.

    Element `k` of a slice that starts at `s` is element `s + k` of the register
    that the slice came from. The result is unknown for any other origin, for a
    negative index into a slice, and for an index outside a known length.
    """
    if not isinstance(origin, HandleOrigin):
        return Origin.top()
    if isinstance(origin.handle, SliceHandle):
        position = index.constant
        if position is not None and position < 0:
            return Origin.top()
        return HandleOrigin(
            ElementHandle(origin.handle.root, origin.handle.start + index)
        )
    if not isinstance(origin.handle, RegisterHandle):
        return Origin.top()
    register = origin.handle
    position = index.constant
    if position is not None and position < 0:
        if register.length is None:
            return Origin.top()
        index = register.length + index
        position = index.constant
    size = None if register.length is None else register.length.constant
    if size is not None and position is not None and not 0 <= position < size:
        return Origin.top()
    return HandleOrigin(ElementHandle(register.root, index))


def slice_of(origin: Origin, start: IndexExpr) -> Origin:
    """Return the origin of the range at `start` of a whole register origin.

    The result is unknown for any other origin.
    """
    if not isinstance(origin, HandleOrigin) or not isinstance(
        origin.handle, RegisterHandle
    ):
        return Origin.top()
    return HandleOrigin(SliceHandle(origin.handle.root, start))


@dataclass(frozen=True)
class Origin(BoundedLattice["Origin"]):
    """Hold what the position check knows about where a value comes from.

    `UnknownOrigin` is the top and `UnreachableOrigin` is the bottom. A
    `HandleOrigin` names one allocation or element, and a `TupleOrigin` holds one
    origin for each tuple field.
    """

    @classmethod
    def top(cls) -> Origin:
        """Return an unknown origin."""
        return UnknownOrigin()

    @classmethod
    def bottom(cls) -> Origin:
        """Return the origin of a value that no execution reaches."""
        return UnreachableOrigin()

    def is_subseteq(self, other: Origin) -> bool:
        """Check whether this origin carries at least the facts of `other`."""
        if (
            isinstance(self, UnreachableOrigin)
            or isinstance(other, UnknownOrigin)
            or self == other
        ):
            return True
        return (
            isinstance(self, TupleOrigin)
            and isinstance(other, TupleOrigin)
            and len(self.fields) == len(other.fields)
            and all(a.is_subseteq(b) for a, b in zip(self.fields, other.fields))
        )

    def join(self, other: Origin) -> Origin:
        """Keep the origin facts that hold for both values."""
        if self.is_subseteq(other):
            return other
        if other.is_subseteq(self):
            return self
        if (
            isinstance(self, TupleOrigin)
            and isinstance(other, TupleOrigin)
            and len(self.fields) == len(other.fields)
        ):
            return TupleOrigin(
                tuple(a.join(b) for a, b in zip(self.fields, other.fields))
            )
        return UnknownOrigin()

    def meet(self, other: Origin) -> Origin:
        """Combine compatible facts, or return unreachable for conflicting ones."""
        if self.is_subseteq(other):
            return self
        if other.is_subseteq(self):
            return other
        if (
            isinstance(self, TupleOrigin)
            and isinstance(other, TupleOrigin)
            and len(self.fields) == len(other.fields)
        ):
            return TupleOrigin(
                tuple(a.meet(b) for a, b in zip(self.fields, other.fields))
            )
        return UnreachableOrigin()

    def roots(self) -> frozenset[Hashable]:
        """Return the allocation roots that this origin identifies exactly."""
        if isinstance(self, HandleOrigin):
            return frozenset({self.handle.root})
        if isinstance(self, TupleOrigin):
            return frozenset(root for item in self.fields for root in item.roots())
        return frozenset()

    def at_call(self, call: ir.Statement, inputs: frozenset[Hashable]) -> Origin:
        """Give each fresh call result a call-specific root, and keep borrowed roots."""
        if isinstance(self, HandleOrigin) and self.handle.root not in inputs:
            return HandleOrigin(replace(self.handle, root=(call, self.handle.root)))
        if isinstance(self, TupleOrigin):
            return TupleOrigin(
                tuple(item.at_call(call, inputs) for item in self.fields)
            )
        return self


@dataclass(frozen=True)
class UnknownOrigin(Origin):
    """Name a value whose origin the check cannot name."""


@dataclass(frozen=True)
class UnreachableOrigin(Origin):
    """Name a value that no execution reaches."""


@dataclass(frozen=True)
class HandleOrigin(Origin):
    """Name the allocation or the element that a value comes from."""

    handle: Handle


@dataclass(frozen=True)
class TupleOrigin(Origin):
    """Hold the origin of each field of a tuple value."""

    fields: tuple[Origin, ...]
