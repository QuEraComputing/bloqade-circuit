"""Bloqade types.

This module defines the basic types used in Bloqade eDSLs.
"""

from abc import ABC
from typing import Any

from kirin import types
from kirin.dialects.ilist import IList, IListType

from bloqade.decoders.dialects.annotate.types import (
    MeasurementResult as MeasurementResult,
    MeasurementResultType as MeasurementResultType,
)


class Qubit(ABC):
    """Runtime representation of a qubit.

    Note:
        This is the base class of more specific qubit types, such as
        a reference to a piece of quantum register in some quantum register
        dialects.
    """

    pass


Register = IList[Qubit, Any]
"""Runtime representation of a qubit register."""

QubitType = types.PyClass(Qubit)
"""Kirin type for a qubit."""


def is_subtype(kind: types.TypeAttribute, expected: types.TypeAttribute) -> bool:
    """Return True if `kind` is a subtype of `expected`.

    Kirin's `is_subseteq` also holds for `Bottom`, the type of a value that type
    inference could not reach. This check treats `Bottom` as a subtype of nothing,
    so a failed type inference fails the check.
    """
    return not isinstance(kind, types.BottomType) and kind.is_subseteq(expected)


def item_type(kind: types.TypeAttribute) -> types.TypeAttribute:
    """Return the item type of the list type `kind`, or `Any` for any other type."""
    if isinstance(kind, types.Generic) and is_subtype(kind, IListType):
        return kind.vars[0]
    return types.Any


def holds_qubits(kind: types.TypeAttribute) -> bool:
    """Return True if the type `kind` holds qubits, such as `IList[Qubit, 3]`."""
    if isinstance(kind, types.BottomType):
        return False
    if is_subtype(kind, QubitType):
        return True
    if isinstance(kind, types.Union):
        return any(holds_qubits(member) for member in kind.types)
    if isinstance(kind, types.TypeVar):
        return holds_qubits(kind.bound)
    if isinstance(kind, types.Generic):
        # The second variable of an `IList` is its length, which holds no qubit.
        members = kind.vars[:1] if is_subtype(kind, IListType) else kind.vars
        return any(holds_qubits(member) for member in members) or (
            kind.vararg is not None and holds_qubits(kind.vararg.typ)
        )
    return False
