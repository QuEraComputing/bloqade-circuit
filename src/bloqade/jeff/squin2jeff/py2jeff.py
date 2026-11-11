"""Replace classical kirin statements with Jeff classical statements."""

import math

from kirin import ir, types
from kirin.dialects import py, ilist
from kirin.dialects.py import len as py_len, slice as py_slice
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.dialects.math import stmts as math_stmts

from bloqade.types import item_type, output_types
from bloqade.constants import constant_int
from bloqade.jeff.forms import SWAPPED, INT_BINARY, FLOAT_UNARY, FLOAT_BINARY
from bloqade.jeff.types import FloatArrayType, is_bit, is_subtype
from bloqade.jeff.dialects import stmts
from bloqade.squin.rewrite.wire.tools import put, replace

from .values import fitted, bitwidth, jeff_type

Values = tuple[ir.SSAValue, ...]


class Classical(RewriteRule):
    """Replace each classical kirin statement with its Jeff form.

    A range, a slice, the constant None and a tuple have no Jeff value. The rule
    leaves them in place. A loop reads the bounds of a range, a call or a return
    reads the fields of a tuple, and dead-code elimination removes the rest.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Rewrite `node` if it is a classical statement with a Jeff form."""
        values = classical_values(node)
        if values is None:
            return RewriteResult()
        replace(node, *values)
        return RewriteResult(has_done_something=True)


def constant(node: py.Constant) -> Values | None:
    """Return the Jeff constant of `node`, or None for a range, a slice or None."""
    match node.value.unwrap():
        case ilist.IList(data=range()) | slice() | None:
            return None
    return (constant_value(node, node.value.unwrap(), node.result.type),)


def constant_value(
    before: ir.Statement, item: object, typ: types.TypeAttribute
) -> ir.SSAValue:
    """Insert the Jeff constant for the Python value `item` of the squin type `typ`.

    The type decides between a bit and an integer, since squin may hold a boolean as
    the integer 1. A tuple becomes a `py.tuple.New` of its members.
    """
    match item:
        case tuple(members):
            outputs = output_types(typ)
            if len(outputs) != len(members):
                outputs = tuple(types.Literal(member) for member in members)
            fields = tuple(
                constant_value(before, member, k) for member, k in zip(members, outputs)
            )
            return put(py.tuple.New(fields), before).result
        case ilist.IList(data=list(members)) if jeff_type(typ) == FloatArrayType or any(
            isinstance(member, float) for member in members
        ):
            floats = tuple(float(member) for member in members)
            return put(stmts.FloatArrayConst(values=floats), before).result
        case ilist.IList(data=list(members)):
            width = bitwidth(item_type(typ))
            ints = tuple(int(member) for member in members)
            return put(stmts.IntArrayConst(values=ints, bitwidth=width), before).result
        case bool() | int() | float() if jeff_type(typ) == types.Bool:
            return put(stmts.ConstInt(value=int(item), bitwidth=1), before).result
        case bool() | int() | float() if jeff_type(typ) == types.Float:
            return put(stmts.ConstFloat(value=float(item)), before).result
        case bool() | int():
            return put(stmts.ConstInt(value=int(item)), before).result
        case float():
            return put(stmts.ConstFloat(value=item), before).result
    raise ir.ValidationError(
        before, f"Jeff has no constant of the type {type(item).__name__}."
    )


def is_float(value: ir.SSAValue) -> bool:
    """Check whether `value` is a float."""
    return is_subtype(value.type, types.Float)


def zero_test(value: ir.SSAValue, before: ir.Statement) -> ir.SSAValue:
    """Insert the bit that is 1 if the number `value` is zero, Python's `not value`."""
    if is_bit(value):
        return put(stmts.IntNot(value), before).result
    if is_float(value):
        zero = put(stmts.ConstFloat(value=0.0), before).result
        return put(stmts.FloatEq(value, zero), before).result
    zero = put(stmts.ConstInt(value=0), before).result
    return put(stmts.IntEq(value, zero), before).result


def as_float(value: ir.SSAValue, before: ir.Statement) -> ir.SSAValue:
    """Return `value` as a float. It must be a float or an integer constant.

    Jeff has no conversion from a runtime integer to a float.
    """
    if is_float(value):
        return value
    if isinstance(owner := value.owner, stmts.ConstInt):
        return put(stmts.ConstFloat(value=float(owner.value)), before).result
    raise ir.ValidationError(
        before, "Jeff cannot convert a runtime integer to a float."
    )


def binary(node: ir.Statement) -> Values:
    """Return the Jeff form of a binary operation or a comparison on two numbers."""
    op = type(node)
    lhs, rhs = node.args
    if not all(is_subtype(value.type, types.Int | types.Float) for value in node.args):
        raise ir.ValidationError(
            node, f"'{node.name}' requires scalar numeric operands."
        )
    if op in SWAPPED:
        op, lhs, rhs = SWAPPED[op], rhs, lhs
    if is_float(lhs) or is_float(rhs):
        table = FLOAT_BINARY
        operands = (as_float(lhs, node), as_float(rhs, node))
    else:
        # Python counts a bool as an int, so a bit beside an int, or a bit in a
        # sum, widens. Two bits under a bitwise operation stay bits.
        table = INT_BINARY
        widest = node.results[0].type.join(lhs.type).join(rhs.type)
        operands = (fitted(lhs, widest, node), fitted(rhs, widest, node))
    if op not in table:
        raise ir.ValidationError(
            node,
            f"Jeff has no numeric form for '{node.name}' with these operand types.",
        )
    made = put(table[op](*operands), node).results[0]
    if op is py.cmp.NotEq:
        return (put(stmts.IntNot(made), node).result,)
    return (made,)


def floored(node: ir.Statement) -> Values:
    """Return the Jeff form of a floor division or a modulo of two integers.

    Jeff rounds a quotient toward zero and Python toward minus infinity. If the
    remainder is nonzero and the operands differ in sign, the quotient drops one
    and the remainder gains the divisor.
    """
    if not all(is_subtype(value.type, types.Int) for value in node.args):
        raise ir.ValidationError(
            node, f"'{node.name}' requires integer operands in Jeff."
        )
    a, b = (fitted(value, types.Int, node) for value in node.args)
    zero = put(stmts.ConstInt(value=0), node).result
    one = put(stmts.ConstInt(value=1), node).result
    remainder = put(stmts.IntRemS(a, b), node).result
    zero_remainder = put(stmts.IntEq(remainder, zero), node).result
    nonzero = put(stmts.IntNot(zero_remainder), node).result
    negative_a = put(stmts.IntLtS(a, zero), node).result
    negative_b = put(stmts.IntLtS(b, zero), node).result
    unlike = put(stmts.IntXor(negative_a, negative_b), node).result
    rounded = put(stmts.IntAnd(nonzero, unlike), node).result
    fix = put(stmts.IntSelect(rounded, one, zero), node).result
    if isinstance(node, py.binop.FloorDiv):
        quotient = put(stmts.IntDivS(a, b), node).result
        return (put(stmts.IntSub(quotient, fix), node).result,)
    correction = put(stmts.IntMul(b, fix), node).result
    return (put(stmts.IntAdd(remainder, correction), node).result,)


def boolop(node: ir.Statement) -> Values:
    """Convert boolean operands whose values match their declared result type."""
    if not all(is_bit(value) for value in node.args):
        raise ir.ValidationError(
            node,
            "Numeric boolean operators require operand selection before wire type inference.",
        )
    lhs, rhs = node.args
    operation = stmts.IntAnd if isinstance(node, py.boolop.And) else stmts.IntOr
    return (put(operation(lhs, rhs), node).result,)


def integer_only(node: ir.Statement, value: ir.SSAValue) -> None:
    """Reject a bool operand, for which Python gives an int result."""
    if is_subtype(value.type, types.Bool):
        raise ir.ValidationError(
            node, f"'{node.name}' on a bool requires Python integer semantics."
        )


def usub(node: py.unary.USub) -> Values:
    """Return the subtraction of the operand from zero."""
    integer_only(node, node.value)
    if is_float(node.value):
        zero = put(stmts.ConstFloat(value=0.0), node).result
        return (put(stmts.FloatSub(zero, node.value), node).result,)
    zero = put(stmts.ConstInt(value=0), node).result
    return (put(stmts.IntSub(zero, node.value), node).result,)


def invert(node: py.unary.Invert) -> Values:
    """Return the bitwise negation of an integer."""
    integer_only(node, node.value)
    return (put(stmts.IntNot(node.value), node).result,)


def absolute(node: py.builtin.Abs) -> Values:
    """Return the absolute value of a number."""
    integer_only(node, node.value)
    if is_float(node.value):
        return (put(stmts.FloatAbs(node.value), node).result,)
    return (put(stmts.IntAbs(node.value), node).result,)


def logarithm(node: math_stmts.log) -> Values:
    """Return the natural logarithm divided by the natural logarithm of the base.

    A constant base gives a constant factor.
    """
    natural = put(stmts.FloatLog(node.x), node).result
    if isinstance(owner := node.base.owner, (stmts.ConstFloat, stmts.ConstInt)):
        if owner.value == math.e:
            return (natural,)
        scale = 1 / math.log(owner.value)
        factor = put(stmts.ConstFloat(value=scale), node).result
        return (put(stmts.FloatMul(natural, factor), node).result,)
    base = put(stmts.FloatLog(as_float(node.base, node)), node).result
    return (put(stmts.FloatDiv(natural, base), node).result,)


def array(node: ilist.New) -> Values:
    """Return a Jeff array of the list members.

    Floats give a float array, bits a 1-bit array and integers a 32-bit array.
    """
    values = tuple(node.values)
    if any(is_subtype(value.type, types.Float) for value in values):
        return (put(stmts.FloatArrayCreate(values), node).result,)
    width = 1 if values and all(is_bit(value) for value in values) else 32
    if width == 32:
        values = tuple(fitted(value, types.Int, node) for value in values)
    return (put(stmts.IntArrayCreate(values, bitwidth=width), node).result,)


def length(node: py_len.Len) -> Values:
    """Return the length of a classical array."""
    if is_subtype(node.value.type, FloatArrayType):
        return (put(stmts.FloatArrayLen(node.value), node).result,)
    return (put(stmts.IntArrayLen(node.value), node).result,)


def item(node: py.indexing.GetItem) -> Values | None:
    """Return a field of a tuple or an element of a classical array.

    A tuple field needs a constant index. The rule leaves a read of a range or a
    slice in place.
    """
    container = node.obj
    if isinstance(container.owner, py.tuple.New):
        if (position := constant_int(node.index)) is None:
            raise ir.ValidationError(
                node, "Jeff requires a tuple read at a constant index."
            )
        return (container.owner.args[position],)
    if isinstance(container.owner, (py.Constant, py_slice.Slice)):
        return None
    if is_subtype(container.type, FloatArrayType):
        return (put(stmts.FloatArrayGet(container, node.index), node).result,)
    width = bitwidth(node.result.type)
    made = stmts.IntArrayGet(container, node.index, bitwidth=width)
    return (put(made, node).result,)


def classical_values(node: ir.Statement) -> Values | None:
    """Return replacement values for a supported classical statement."""
    match node:
        case py.Constant():
            return constant(node)
        case py.binop.FloorDiv() | py.binop.Mod():
            return floored(node)
        case py.boolop.And() | py.boolop.Or():
            return boolop(node)
        case py.unary.USub():
            return usub(node)
        case py.unary.Not():
            return (zero_test(node.value, node),)
        case py.unary.Invert():
            return invert(node)
        case py.builtin.Abs():
            return absolute(node)
        case math_stmts.log():
            return logarithm(node)
        case math_stmts.pow() | math_stmts.atan2():
            return (put(FLOAT_BINARY[type(node)](*node.args), node).results[0],)
        case ilist.New():
            return array(node)
        case py_len.Len():
            return length(node)
        case py.indexing.GetItem():
            return item(node)
        case py.assign.Alias():
            return (node.value,)
    if type(node) in INT_BINARY or type(node) in FLOAT_BINARY or type(node) in SWAPPED:
        return binary(node)
    if (unary := FLOAT_UNARY.get(type(node))) is not None:
        return (put(unary(node.args[0]), node).results[0],)
    return None
