"""Hold what the index analysis knows about one value."""

from __future__ import annotations

from dataclasses import dataclass

from kirin.lattice import BoundedLattice

from .expr import IndexExpr


@dataclass(frozen=True)
class Index(BoundedLattice["Index"]):
    """Hold the index expression fact of one value.

    `UnknownIndex` is the top, `UnreachableIndex` is the bottom, and `KnownIndex`
    holds an index expression.
    """

    @classmethod
    def top(cls) -> Index:
        """Return the fact of a value without an index expression."""
        return UnknownIndex()

    @classmethod
    def bottom(cls) -> Index:
        """Return the fact of a value that no execution reaches."""
        return UnreachableIndex()

    def is_subseteq(self, other: Index) -> bool:
        """Return True if `other` holds no more than this fact."""
        return (
            isinstance(self, UnreachableIndex)
            or isinstance(other, UnknownIndex)
            or self == other
        )

    def join(self, other: Index) -> Index:
        """Return the fact that holds for both values."""
        if self.is_subseteq(other):
            return other
        if other.is_subseteq(self):
            return self
        return UnknownIndex()

    def meet(self, other: Index) -> Index:
        """Return the fact that implies both facts, or `UnreachableIndex` if none does."""
        if self.is_subseteq(other):
            return self
        if other.is_subseteq(self):
            return other
        return UnreachableIndex()


@dataclass(frozen=True, repr=False)
class UnknownIndex(Index):
    """Name the fact of a value without an index expression."""

    def __repr__(self) -> str:
        """Return `unknown`, which Kirin prints next to the value."""
        return "unknown"


@dataclass(frozen=True, repr=False)
class UnreachableIndex(Index):
    """Name the fact of a value that no execution reaches."""

    def __repr__(self) -> str:
        """Return `unreachable`, which Kirin prints next to the value."""
        return "unreachable"


@dataclass(frozen=True, repr=False)
class KnownIndex(Index):
    """Hold the index expression of a value."""

    expr: IndexExpr

    def __repr__(self) -> str:
        """Return the index expression, such as `2*%n - 1`."""
        return repr(self.expr)
