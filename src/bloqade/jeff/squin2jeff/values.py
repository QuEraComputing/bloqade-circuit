"""Convert squin wire types and values to Jeff types and values during rewrites."""

import math

from kirin import ir, types
from kirin.dialects import ilist

from bloqade.types import MeasurementResultType, is_subtype
from bloqade.jeff.types import WireType, IntArrayType, FloatArrayType, qureg
from bloqade.jeff.dialects import stmts
from bloqade.squin.wire.types import (
    WireType as SquinWireType,
    RegisterType,
    register_length,
)
from bloqade.squin.rewrite.wire.tools import put


def jeff_type(typ: types.TypeAttribute) -> types.TypeAttribute:
    """Return the Jeff type of a value of the squin type `typ`.

    A register keeps its static length, so `Register[3]` becomes `qureg(3)`.
    """
    if isinstance(typ, types.Union):
        # A union of a bit and an integer, such as a measurement result that a loop
        # adds 1 to, is an integer.
        members = [jeff_type(member) for member in typ.types]
        joined = members[0]
        for member in members[1:]:
            joined = joined.join(member)
        return joined
    if isinstance(typ, types.Literal):
        match typ.data:
            case bool():
                return types.Bool
            case int():
                return types.Int
            case float():
                return types.Float
            case ilist.IList(data=list(items)) if any(
                isinstance(item, float) for item in items
            ):
                return FloatArrayType
            case ilist.IList():
                return IntArrayType
    if is_subtype(typ, SquinWireType):
        return WireType
    if is_subtype(typ, MeasurementResultType):
        # Jeff measures to one bit, so the conversion assumes that no qubit is lost.
        return types.Bool
    if is_subtype(typ, RegisterType):
        return qureg(register_length(typ))

    if is_subtype(typ, ilist.IListType[types.Float, types.Any]):
        return FloatArrayType
    if is_subtype(typ, ilist.IListType):
        return IntArrayType
    return typ


def joined(*values: ir.SSAValue) -> types.TypeAttribute:
    """Return the Jeff type of a value that can be any of `values`.

    A bit joined with an integer is an integer.
    """
    typ = values[0].type
    for value in values[1:]:
        typ = typ.join(value.type)
    return jeff_type(typ)


def bitwidth(elements: types.TypeAttribute) -> int:
    """Return the Jeff bitwidth of an integer array with the element type `elements`.

    A measurement result or a boolean is one bit, any other integer is 32 bits.
    """
    if is_subtype(elements, MeasurementResultType) or is_subtype(elements, types.Bool):
        return 1
    return 32


def fitted(
    value: ir.SSAValue, typ: types.TypeAttribute, before: ir.Statement
) -> ir.SSAValue:
    """Return the Jeff `value` as the squin type `typ` expects it.

    Squin joins a bit and an integer to an integer. Jeff has no conversion, so a bit
    in an integer position becomes `int_select(bit, 1, 0)`. The value can still be a
    wire value, such as a measurement result, so the check reads its Jeff type.
    """
    if jeff_type(value.type) == types.Bool and jeff_type(typ) == types.Int:
        one = put(stmts.ConstInt(value=1), before).result
        zero = put(stmts.ConstInt(value=0), before).result
        return put(stmts.IntSelect(value, one, zero), before).result
    return value


def radians(turns: ir.SSAValue, before: ir.Statement) -> ir.SSAValue:
    """Return the angle in radians of the squin gate angle `turns`."""
    full = put(stmts.ConstFloat(value=2 * math.pi), before).result
    return put(stmts.FloatMul(turns, full), before).result
