"""Map squin wire types to Jeff types and insert Jeff statements during rewrites."""

import math
from typing import TypeVar

from kirin import ir, types
from kirin.dialects import ilist

from bloqade.types import MeasurementResultType, is_subtype
from bloqade.jeff.types import WireType, IntArrayType, FloatArrayType, qureg, is_bit
from bloqade.jeff.dialects import stmts
from bloqade.squin.wire.types import (
    WireType as SquinWireType,
    RegisterType,
    register_length,
)
from bloqade.squin.rewrite.wire.driver import put as insert, replace as replace

StatementT = TypeVar("StatementT", bound=ir.Statement)


def jeff_kind(kind: types.TypeAttribute) -> types.TypeAttribute:
    """Return the Jeff type of a value of the squin type `kind`.

    A register keeps its static length, so `Register[3]` becomes `qureg(3)`.
    """
    if isinstance(kind, types.Literal):
        match kind.data:
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
    if is_subtype(kind, SquinWireType):
        return WireType
    if is_subtype(kind, MeasurementResultType):
        # Jeff measures to one bit, so the conversion assumes that no qubit is lost.
        return types.Bool
    if is_subtype(kind, RegisterType):
        return qureg(register_length(kind))
    if is_subtype(kind, ilist.IListType[types.Float, types.Any]):
        return FloatArrayType
    if is_subtype(kind, ilist.IListType):
        return IntArrayType
    return kind


def bitwidth(elements: types.TypeAttribute) -> int:
    """Return the Jeff bitwidth of an integer array with the element type `elements`.

    A measurement result or a boolean is one bit, any other integer is 32 bits.
    """
    if is_subtype(elements, MeasurementResultType) or is_subtype(elements, types.Bool):
        return 1
    return 32


def put(stmt: StatementT, before: ir.Statement) -> StatementT:
    """Insert `stmt` before the statement `before` and return `stmt`.

    An integer operation on bits gives a bit, which the statement types `Bool`.
    """
    if isinstance(stmt, (stmts.IntUnary, stmts.IntBinary)) and is_bit(stmt.args[0]):
        stmt.results[0].type = types.Bool
    return insert(stmt, before)


def fitted(
    value: ir.SSAValue, kind: types.TypeAttribute, before: ir.Statement
) -> ir.SSAValue:
    """Return the Jeff `value` as the squin type `kind` expects it.

    Squin joins a bit and an integer to an integer. Jeff has no conversion, so a bit
    in an integer position becomes `int_select(bit, 1, 0)`. The value can still be a
    wire value, such as a measurement result, so the check reads its Jeff type.
    """
    if jeff_kind(value.type) == types.Bool and jeff_kind(kind) == types.Int:
        one = put(stmts.ConstInt(value=1), before).result
        zero = put(stmts.ConstInt(value=0), before).result
        return put(stmts.IntSelect(value, one, zero), before).result
    return value


def radians(turns: ir.SSAValue, before: ir.Statement) -> ir.SSAValue:
    """Return the angle in radians of the squin gate angle `turns`."""
    full = put(stmts.ConstFloat(value=2 * math.pi), before).result
    return put(stmts.FloatMul(turns, full), before).result
