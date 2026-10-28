"""Define the types of the jeff dialect.

A `Wire` is a linear value that stands for one qubit at one point in the program.
Every operation consumes its input wires and produces fresh wires.
A program must consume each wire exactly once.
A `Qureg` is a linear register of qubits with dynamic indexing.
Extracting a qubit leaves its slot empty until an insert fills the slot again.
`IntArray` and `FloatArray` mirror jeff's classical array types.
An `IntArray` of bitwidth 1 holds measurement bits.

A jeff value family is one of the type groups in `FAMILIES`, such as integers or wires.
"""

from kirin import ir, types


class Wire:
    """A marker class that names the linear type of one qubit."""


class Qureg:
    """A marker class that names the linear type of a qubit register."""


class IntArray:
    """A marker class that names the type of an integer array."""


class FloatArray:
    """A marker class that names the type of a float array."""


WireType = types.PyClass(Wire)
QuregType = types.PyClass(Qureg)


def qureg(length: int | types.TypeVar | None) -> types.TypeAttribute:
    """Build the register type for a length.

    If the length is an integer, the type carries that static length.
    If the length is a type variable, the variable names the runtime length.
    If the length is None, the type is a register of unknown length.
    """
    if length is None:
        return QuregType
    if isinstance(length, int):
        return types.Generic(Qureg, types.Literal(length))
    return types.Generic(Qureg, length)


def qureg_length(register: types.TypeAttribute) -> int | None:
    """Return the static length of a register type, or None if it has no static length.

    For example, `qureg(3)` gives 3 and `QuregType` gives None.
    """
    if isinstance(register, types.Generic) and register.vars:
        length = register.vars[0]
        if isinstance(length, types.Literal) and isinstance(length.data, int):
            return length.data
    return None


def is_subtype(kind: types.TypeAttribute, expected: types.TypeAttribute) -> bool:
    """Return True if `kind` is a subtype of `expected`."""
    return not isinstance(kind, types.BottomType) and kind.is_subseteq(expected)


def is_linear(kind: types.TypeAttribute) -> bool:
    """Check whether a type is linear.

    Wires and registers are the linear types. A program must consume each linear
    value exactly once.
    """
    return is_subtype(kind, WireType) or is_subtype(kind, QuregType)


def is_bit(value: ir.SSAValue) -> bool:
    """Check whether a value is a jeff 1-bit integer.

    Kirin types a jeff bit as `Bool`.
    """
    return is_subtype(value.type, types.Bool)


def family(kind: types.TypeAttribute) -> types.TypeAttribute | None:
    """Return the jeff value family of a type, or None if the type belongs to no family.

    The loop tests `Bool` before `Int`, because every bit is also an integer.
    """
    for candidate in FAMILIES:
        if is_subtype(kind, candidate):
            return candidate
    return None


IntArrayType = types.PyClass(IntArray)
FloatArrayType = types.PyClass(FloatArray)

FAMILIES = (
    types.Bool,
    types.Int,
    types.Float,
    WireType,
    QuregType,
    IntArrayType,
    FloatArrayType,
)
"""The function `family` tests the jeff value families in the order of this tuple."""


def same_family(actual: types.TypeAttribute, expected: types.TypeAttribute) -> bool:
    """Check whether two types belong to the same jeff value family.

    If `actual` belongs to no family, the result is False.
    """
    kind = family(actual)
    return kind is not None and kind is family(expected)


def same_length(actual: types.TypeAttribute, expected: types.TypeAttribute) -> bool:
    """Check that two register types agree on their length when both carry one."""
    first, second = qureg_length(actual), qureg_length(expected)
    return first is None or second is None or first == second
