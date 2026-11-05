"""Define the linear types of the squin wire dialect.

A `Wire` stands for one qubit at one point in the program. A statement consumes
its input wires and returns new wires, so each wire has exactly one use.

A `Register` stands for a list of qubits. `Borrow` lends one qubit of a register to
a wire, and `Release` puts the wire back. A register type can carry a static number
of qubits, such as `Register[3]`.
"""

from kirin import types

from bloqade.types import contains, is_subtype


class Wire:
    """Name the linear type of one qubit."""


class Register:
    """Name the linear type of a list of qubits."""


WireType = types.PyClass(Wire)
RegisterType = types.PyClass(Register)


def register_type(length: int | None) -> types.TypeAttribute:
    """Return the type of a register of `length` qubits.

    The result is `RegisterType` if the length is None.
    """
    if length is None:
        return RegisterType
    return types.Generic(Register, types.Literal(length))


def literal_length(length: types.TypeAttribute) -> int | None:
    """Return the integer of the length type `length`, such as 3 for `Literal(3)`."""
    if isinstance(length, types.Literal) and isinstance(length.data, int):
        return length.data
    return None


def register_length(typ: types.TypeAttribute) -> int | None:
    """Return the static number of qubits of a register type, or None."""
    if isinstance(typ, types.Generic) and is_subtype(typ, RegisterType) and typ.vars:
        return literal_length(typ.vars[0])
    return None


def is_linear(typ: types.TypeAttribute) -> bool:
    """Return True if a value of the type `typ` must have exactly one use."""
    return is_subtype(typ, WireType) or is_subtype(typ, RegisterType)


def contains_linear(typ: types.TypeAttribute) -> bool:
    """Return whether the type contains a wire or register at any depth."""
    return contains(typ, is_linear)


def nests_linear(typ: types.TypeAttribute) -> bool:
    """Check whether the type holds a wire or a register inside a container."""
    return contains_linear(typ) and not is_linear(typ)


def linear_paths(typ: types.TypeAttribute) -> tuple[tuple[int, ...], ...]:
    """Return the tuple paths of every wire and register in a supported type.

    Quantum containers must have fixed tuple fields so each field has an owner.
    """
    if is_linear(typ):
        return ((),)
    if not contains_linear(typ):
        return ()
    if (
        isinstance(typ, types.Generic)
        and is_subtype(typ, types.Tuple)
        and typ.vararg is None
    ):
        return tuple(
            (index, *path)
            for index, member in enumerate(typ.vars)
            for path in linear_paths(member)
        )
    raise ValueError("Quantum containers must use fixed tuple fields.")
