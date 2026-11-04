"""This module defines the linear types of the squin wire dialect.

A `Wire` stands for one qubit at one point in the program. A statement consumes
its input wires and returns new wires, so each wire has exactly one use.

A `Register` stands for a list of qubits. `Borrow` takes one qubit out of a
register as a wire, and `Release` puts the wire back. A register type can carry a
static number of qubits, such as `Register[3]`.
"""

import math

from kirin import types
from kirin.dialects import ilist

from bloqade.types import QubitType, is_subtype


class Wire:
    """A marker class that names the linear type of one qubit."""


class Register:
    """A marker class that names the linear type of a list of qubits."""


WireType = types.PyClass(Wire)
RegisterType = types.PyClass(Register)


def register_type(length: int | None) -> types.TypeAttribute:
    """Return the type of a register of `length` qubits.

    The result is `RegisterType` if the length is None.
    """
    if length is None:
        return RegisterType
    return types.Generic(Register, types.Literal(length))


def register_length(kind: types.TypeAttribute) -> int | None:
    """Return the static number of qubits of a register type, or None."""
    if isinstance(kind, types.Generic) and is_subtype(kind, RegisterType) and kind.vars:
        length = kind.vars[0]
        if isinstance(length, types.Literal) and isinstance(length.data, int):
            return length.data
    return None


def is_linear(kind: types.TypeAttribute) -> bool:
    """Return True if a value of the type `kind` must have exactly one use."""
    if isinstance(kind, types.BottomType):
        return False
    return is_subtype(kind, WireType) or is_subtype(kind, RegisterType)


def contains_linear(kind: types.TypeAttribute) -> bool:
    """Return whether the type contains a wire or register at any depth."""
    if is_linear(kind):
        return True
    if isinstance(kind, types.Union):
        return any(contains_linear(member) for member in kind.types)
    if isinstance(kind, types.TypeVar):
        return contains_linear(kind.bound)
    if isinstance(kind, types.Generic):
        return any(contains_linear(member) for member in kind.vars) or (
            kind.vararg is not None and contains_linear(kind.vararg.typ)
        )
    return False


def linear_paths(kind: types.TypeAttribute) -> tuple[tuple[int, ...], ...]:
    """Return the tuple paths of every wire and register in a supported type.

    Quantum containers must have fixed tuple fields so each field has an owner.
    """
    if is_linear(kind):
        return ((),)
    if not contains_linear(kind):
        return ()
    if (
        isinstance(kind, types.Generic)
        and is_subtype(kind, types.Tuple)
        and kind.vararg is None
    ):
        return tuple(
            (index, *path)
            for index, member in enumerate(kind.vars)
            for path in linear_paths(member)
        )
    raise ValueError("Quantum containers must use fixed tuple fields.")


def quantum_type(kind: types.TypeAttribute) -> types.TypeAttribute | None:
    """Return the linear type of a scalar qubit or a nested qubit register."""
    if isinstance(kind, types.BottomType):
        return None
    if is_subtype(kind, QubitType) or is_subtype(kind, WireType):
        return WireType
    if is_subtype(kind, RegisterType):
        return RegisterType
    if isinstance(kind, types.Generic) and is_subtype(kind, ilist.IListType):
        if quantum_type(kind.vars[0]) is not None:
            return RegisterType
    return None


def typed_length(kind: types.TypeAttribute) -> int | None:
    """Return a list's declared constant length, if its type supplies one."""
    if isinstance(kind, types.Generic) and is_subtype(kind, ilist.IListType):
        length = kind.vars[1]
        if isinstance(length, types.Literal) and isinstance(length.data, int):
            return length.data
    return None


def register_shape(kind: types.TypeAttribute) -> tuple[int | None, ...]:
    """Return the source register dimensions in outer-to-inner order."""
    shape = []
    while isinstance(kind, types.Generic) and is_subtype(kind, ilist.IListType):
        shape.append(typed_length(kind))
        kind = kind.vars[0]
    return tuple(shape)


def parameter_type(kind: types.TypeAttribute) -> types.TypeAttribute:
    """Return the wire type of a function parameter of the source type `kind`.

    A register keeps its number of qubits if the source type gives every
    dimension. For example, `IList[IList[Qubit, 2], 3]` becomes `Register[6]`.
    """
    linear = quantum_type(kind)
    if linear is None:
        return kind
    shape = register_shape(kind)
    if linear == RegisterType and shape and all(size is not None for size in shape):
        return register_type(math.prod(size for size in shape if size is not None))
    return linear
