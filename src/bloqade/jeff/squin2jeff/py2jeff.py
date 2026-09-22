"""This module holds the rules that emit jeff classical statements for kirin ones."""

# The squin gate statements and the kirin `py` statements derive from base classes
# that a bare `@statement` decorates, which pyright reads as functions. A rule that
# stacks `interp.impl` for several of them then fails the argument check.
# pyright: reportArgumentType=false


import math

from kirin import ir, types, interp
from kirin.dialects import py, math as math_dialect, ilist
from kirin.dialects.py import len as py_len
from kirin.dialects.math import stmts as math_stmts
from kirin.dialects.ilist import stmts as ilist_stmts

from bloqade.constants import constant_int
from bloqade.jeff.forms import (
    SWAPPED,
    INT_BINARY,
    FLOAT_UNARY,
    FLOAT_BINARY,
)
from bloqade.jeff.types import FloatArrayType, is_bit, is_subtype
from bloqade.jeff.dialects import stmts
from bloqade.analysis.reference import Members, Register
from bloqade.jeff.dialects.stmts.call import declared_outputs

from .linearize import KEY, Frame, Value, Linearize, bitwidth, elements, jeff_kind


@py.constant.dialect.register(key=KEY)
class _Constant(interp.MethodTable):
    """A method table that emits jeff constants."""

    @interp.impl(py.Constant)
    def constant(
        self, emit: Linearize, frame: Frame, stmt: py.Constant
    ) -> interp.StatementResult[Value]:
        """Emit a number, a bit, a list or a tuple, and give a range no value."""
        match stmt.value.unwrap():
            case ilist.IList(data=range()):
                return (None,)
        return (_constant(frame, stmt.value.unwrap(), stmt.result.type),)


def _constant(frame: Frame, item: object, kind: types.TypeAttribute) -> Value:
    """Return the jeff constant for the Python value `item` of the squin type `kind`.

    The type decides between a bit and an integer, since squin may hold a
    boolean as the integer 1. A tuple typed without its members takes the
    Python type of each member.
    """
    match item:
        case tuple(items):
            kinds = declared_outputs(kind)
            if len(kinds) != len(items):
                kinds = tuple(types.Literal(member) for member in items)
            return tuple(_constant(frame, member, k) for member, k in zip(items, kinds))
        case ilist.IList(data=list(items)) if jeff_kind(kind) == FloatArrayType or any(
            isinstance(member, float) for member in items
        ):
            values = tuple(float(member) for member in items)
            return frame.push(stmts.FloatArrayConst(values=values)).result
        case ilist.IList(data=list(items)):
            width = bitwidth(elements(kind))
            values = tuple(int(member) for member in items)
            made = stmts.IntArrayConst(values=values, bitwidth=width)
            return frame.push(made).result
        case bool() | int() | float() if jeff_kind(kind) == types.Bool:
            return frame.push(stmts.ConstInt(value=int(item), bitwidth=1)).result
        case bool() | int() | float() if jeff_kind(kind) == types.Float:
            return frame.push(stmts.ConstFloat(value=float(item))).result
        case bool() | int():
            return frame.push(stmts.ConstInt(value=int(item))).result
        case float():
            return frame.push(stmts.ConstFloat(value=item)).result
    raise interp.InterpreterError(f"a constant of type {type(item).__name__}")


def _array(
    values: tuple[ir.SSAValue, ...],
) -> stmts.IntArrayCreate | stmts.FloatArrayCreate:
    """Return the jeff array statement that holds the jeff `values`.

    Floats give a float array, bits a 1-bit array and integers a 32-bit array.
    """
    if any(is_subtype(v.type, types.Float) for v in values):
        return stmts.FloatArrayCreate(values)
    if values and all(is_bit(v) for v in values):
        return stmts.IntArrayCreate(values, bitwidth=1)
    return stmts.IntArrayCreate(values, bitwidth=32)


def _is_float(value: ir.SSAValue) -> bool:
    """Return True if the squin value `value` is a float."""
    return value.type.is_subseteq(types.Float)


def _zero_test(frame: Frame, value: ir.SSAValue) -> ir.SSAValue:
    """Return the jeff bit that is 1 if the squin number `value` is zero.

    This bit is Python's `not value`.
    """
    scalar = frame.scalar(value)
    if is_bit(value):
        return frame.push(stmts.IntNot(scalar)).result
    if _is_float(value):
        zero = frame.push(stmts.ConstFloat(value=0.0)).result
        return frame.push(stmts.FloatEq(scalar, zero)).result
    zero = frame.push(stmts.ConstInt(value=0)).result
    return frame.push(stmts.IntEq(scalar, zero)).result


def _truth(frame: Frame, value: ir.SSAValue) -> ir.SSAValue:
    """Return the jeff bit that is 1 if the squin number `value` is nonzero.

    This bit is Python's `bool(value)`.
    """
    if is_bit(value):
        return frame.scalar(value)
    return frame.push(stmts.IntNot(_zero_test(frame, value))).result


def _as_float(frame: Frame, value: ir.SSAValue) -> ir.SSAValue:
    """Return the jeff float of `value`, which is a float or an integer constant.

    Jeff has no conversion from an integer to a float, so the validation refuses
    any other integer operand of a float operation.
    """
    match value.owner:
        case py.Constant(value=constant) if not _is_float(value):
            return frame.push(stmts.ConstFloat(value=float(constant.unwrap()))).result
    return frame.scalar(value)


class _Binary(interp.MethodTable):
    """A method table that emits jeff arithmetic for a kirin statement on two values."""

    def binary(
        self, emit: Linearize, frame: Frame, stmt: ir.Statement
    ) -> interp.StatementResult[Value]:
        """Emit the jeff statement of a binary operation, comparison or boolean op.

        A `+` of two lists of qubits is a literal list, which its roots name.
        """
        if isinstance(emit.refs.get(stmt.results[0]), Members):
            return (None,)
        kind = type(stmt)
        lhs, rhs = stmt.args
        if kind in SWAPPED:
            kind, lhs, rhs = SWAPPED[kind], rhs, lhs
        if _is_float(lhs) or _is_float(rhs):
            table = FLOAT_BINARY
            operands = (_as_float(frame, lhs), _as_float(frame, rhs))
        else:
            # Python counts a bool as an int, so a bit beside an int, or a bit
            # in a sum, widens. Two bits under a bitwise operation stay bits.
            table = INT_BINARY
            widest = stmt.results[0].type.join(lhs.type).join(rhs.type)
            operands = (
                emit.fitted(frame, frame.scalar(lhs), widest),
                emit.fitted(frame, frame.scalar(rhs), widest),
            )
        made = frame.push(table[kind](*operands)).results[0]
        if kind is py.cmp.NotEq:
            return (frame.push(stmts.IntNot(made)).result,)
        return (made,)


@py.binop.dialect.register(key=KEY)
class _BinOp(_Binary):
    """A method table that emits jeff arithmetic."""

    @interp.impl(py.binop.Add)
    @interp.impl(py.binop.Sub)
    @interp.impl(py.binop.Mult)
    @interp.impl(py.binop.Pow)
    @interp.impl(py.binop.LShift)
    @interp.impl(py.binop.BitAnd)
    @interp.impl(py.binop.BitOr)
    @interp.impl(py.binop.BitXor)
    def binop(
        self, emit: Linearize, frame: Frame, stmt: ir.Statement
    ) -> interp.StatementResult[Value]:
        """Emit the jeff arithmetic statement."""
        return self.binary(emit, frame, stmt)

    @interp.impl(py.binop.FloorDiv)
    @interp.impl(py.binop.Mod)
    def floored(
        self, emit: Linearize, frame: Frame, stmt: py.binop.FloorDiv | py.binop.Mod
    ) -> interp.StatementResult[Value]:
        """Emit a floor division or a modulo of two integers.

        Jeff rounds a quotient toward zero and Python toward minus infinity. If
        the remainder is nonzero and the operands differ in sign, the quotient
        drops one and the remainder gains the divisor.
        """
        a, b = frame.scalar(stmt.lhs), frame.scalar(stmt.rhs)
        zero = frame.push(stmts.ConstInt(value=0)).result
        one = frame.push(stmts.ConstInt(value=1)).result
        remainder = frame.push(stmts.IntRemS(a, b)).result
        zero_remainder = frame.push(stmts.IntEq(remainder, zero)).result
        nonzero = frame.push(stmts.IntNot(zero_remainder)).result
        negative_a = frame.push(stmts.IntLtS(a, zero)).result
        negative_b = frame.push(stmts.IntLtS(b, zero)).result
        unlike = frame.push(stmts.IntXor(negative_a, negative_b)).result
        rounded = frame.push(stmts.IntAnd(nonzero, unlike)).result
        fix = frame.push(stmts.IntSelect(rounded, one, zero)).result
        if isinstance(stmt, py.binop.FloorDiv):
            quotient = frame.push(stmts.IntDivS(a, b)).result
            return (frame.push(stmts.IntSub(quotient, fix)).result,)
        correction = frame.push(stmts.IntMul(b, fix)).result
        return (frame.push(stmts.IntAdd(remainder, correction)).result,)


@py.cmp.dialect.register(key=KEY)
class _Cmp(_Binary):
    """A method table that emits jeff comparisons."""

    @interp.impl(py.cmp.Eq)
    @interp.impl(py.cmp.NotEq)
    @interp.impl(py.cmp.Lt)
    @interp.impl(py.cmp.LtE)
    @interp.impl(py.cmp.Gt)
    @interp.impl(py.cmp.GtE)
    def cmp(
        self, emit: Linearize, frame: Frame, stmt: ir.Statement
    ) -> interp.StatementResult[Value]:
        """Emit the jeff comparison statement."""
        return self.binary(emit, frame, stmt)


@py.boolop.dialect.register(key=KEY)
class _BoolOp(interp.MethodTable):
    """A method table that emits jeff bit operations for boolean operators."""

    @interp.impl(py.boolop.And)
    @interp.impl(py.boolop.Or)
    def boolop(
        self, emit: Linearize, frame: Frame, stmt: ir.Statement
    ) -> interp.StatementResult[Value]:
        """Emit the bit operation on the truth bit of each operand.

        Kirin types the result as a bool, so the result is the truth bit of the
        operand that Python returns. A bitwise operation on the operands
        themselves is wrong: `2 and 1` is true, but `2 & 1` is 0.
        """
        lhs, rhs = (_truth(frame, value) for value in stmt.args)
        operation = stmts.IntAnd if isinstance(stmt, py.boolop.And) else stmts.IntOr
        return (frame.push(operation(lhs, rhs)).result,)


@py.unary.dialect.register(key=KEY)
class _Unary(interp.MethodTable):
    """A method table that emits jeff statements for unary operators."""

    @interp.impl(py.unary.USub)
    def usub(
        self, emit: Linearize, frame: Frame, stmt: py.unary.USub
    ) -> interp.StatementResult[Value]:
        """Emit a subtraction from zero.

        The validation refuses `-` on a bool, since Python gives an int there.
        """
        value = frame.scalar(stmt.value)
        if _is_float(stmt.value):
            zero = frame.push(stmts.ConstFloat(value=0.0)).result
            return (frame.push(stmts.FloatSub(zero, value)).result,)
        zero = frame.push(stmts.ConstInt(value=0)).result
        return (frame.push(stmts.IntSub(zero, value)).result,)

    @interp.impl(py.unary.Not)
    def not_(
        self, emit: Linearize, frame: Frame, stmt: py.unary.Not
    ) -> interp.StatementResult[Value]:
        """Emit the test that the operand is zero, which is Python's `not`."""
        return (_zero_test(frame, stmt.value),)

    @interp.impl(py.unary.Invert)
    def invert(
        self, emit: Linearize, frame: Frame, stmt: py.unary.Invert
    ) -> interp.StatementResult[Value]:
        """Emit the bitwise negation of an integer.

        The validation refuses `~` on a bool, since Python gives an int there.
        """
        return (frame.push(stmts.IntNot(frame.scalar(stmt.value))).result,)


@py.builtin.dialect.register(key=KEY)
class _Builtin(interp.MethodTable):
    """A method table that emits jeff statements for Python builtins."""

    @interp.impl(py.builtin.Abs)
    def abs_(
        self, emit: Linearize, frame: Frame, stmt: py.builtin.Abs
    ) -> interp.StatementResult[Value]:
        """Emit the absolute value."""
        value = frame.scalar(stmt.value)
        if _is_float(stmt.value):
            return (frame.push(stmts.FloatAbs(value)).result,)
        return (frame.push(stmts.IntAbs(value)).result,)


@math_dialect.dialect.register(key=KEY)
class _Math(interp.MethodTable):
    """A method table that emits jeff float functions."""

    @interp.impl(math_stmts.sqrt)
    @interp.impl(math_stmts.fabs)
    @interp.impl(math_stmts.ceil)
    @interp.impl(math_stmts.floor)
    @interp.impl(math_stmts.exp)
    @interp.impl(math_stmts.sin)
    @interp.impl(math_stmts.cos)
    @interp.impl(math_stmts.tan)
    @interp.impl(math_stmts.asin)
    @interp.impl(math_stmts.acos)
    @interp.impl(math_stmts.atan)
    @interp.impl(math_stmts.sinh)
    @interp.impl(math_stmts.cosh)
    @interp.impl(math_stmts.tanh)
    @interp.impl(math_stmts.asinh)
    @interp.impl(math_stmts.atanh)
    @interp.impl(math_stmts.isnan)
    @interp.impl(math_stmts.isinf)
    def unary(
        self, emit: Linearize, frame: Frame, stmt: ir.Statement
    ) -> interp.StatementResult[Value]:
        """Emit the jeff float function of one argument."""
        made = frame.push(FLOAT_UNARY[type(stmt)](frame.scalar(stmt.args[0])))
        return (made.results[0],)

    @interp.impl(math_stmts.pow)
    @interp.impl(math_stmts.atan2)
    def binary(
        self, emit: Linearize, frame: Frame, stmt: ir.Statement
    ) -> interp.StatementResult[Value]:
        """Emit the jeff float function of two arguments."""
        lhs, rhs = (frame.scalar(v) for v in stmt.args)
        return (frame.push(FLOAT_BINARY[type(stmt)](lhs, rhs)).results[0],)

    @interp.impl(math_stmts.log)
    def log(
        self, emit: Linearize, frame: Frame, stmt: math_stmts.log
    ) -> interp.StatementResult[Value]:
        """Emit the natural logarithm, scaled by the constant base.

        Jeff has no float division, so the validation refuses a runtime base.
        """
        natural = frame.push(stmts.FloatLog(frame.scalar(stmt.x))).result
        match stmt.base.owner:
            case py.Constant(value=constant) if constant.unwrap() == math.e:
                return (natural,)
            case py.Constant(value=constant):
                scale = 1 / math.log(constant.unwrap())
                factor = frame.push(stmts.ConstFloat(value=scale)).result
                return (frame.push(stmts.FloatMul(natural, factor)).result,)
        raise interp.InterpreterError("a logarithm with a runtime base")


@py.tuple.dialect.register(key=KEY)
class _Tuple(interp.MethodTable):
    """A method table that keeps a tuple as a tuple of jeff values."""

    @interp.impl(py.tuple.New)
    def new(
        self, emit: Linearize, frame: Frame, stmt: py.tuple.New
    ) -> interp.StatementResult[Value]:
        """Return the values of the members."""
        return (frame.values(stmt.args),)


@ilist.dialect.register(key=KEY)
class _IList(interp.MethodTable):
    """A method table that builds a jeff array for a classical list."""

    @interp.impl(ilist.New)
    def new(
        self, emit: Linearize, frame: Frame, stmt: ilist.New
    ) -> interp.StatementResult[Value]:
        """Return the array of the members, or None for a list that roots name."""
        if isinstance(emit.refs[stmt.result], Members):
            return (None,)
        values = tuple(frame.scalar(v) for v in stmt.values)
        return (frame.push(_array(values)).result,)

    @interp.impl(ilist_stmts.Range)
    def range_(
        self, emit: Linearize, frame: Frame, stmt: ilist_stmts.Range
    ) -> interp.StatementResult[Value]:
        """Give a range no value, because a loop reads its bounds."""
        return (None,)


@py_len.dialect.register(key=KEY)
class _Len(interp.MethodTable):
    """A method table that reads the length of a jeff array."""

    @interp.impl(py_len.Len)
    def len_(
        self, emit: Linearize, frame: Frame, stmt: py_len.Len
    ) -> interp.StatementResult[Value]:
        """Return the length of the array, or the number of qubits of a list."""
        match emit.refs[stmt.value]:
            case Register(root) as ref if emit.analysis.items(ref) is None:
                measured = frame.push(stmts.RegLength(frame.wire(root)))
                frame.wires[root] = measured.result_reg
                return (measured.length,)
            case Register() | Members():
                count = len(emit.qubits(stmt.value))
                return (frame.push(stmts.ConstInt(value=count)).result,)
        array = frame.scalar(stmt.value)
        if is_subtype(array.type, FloatArrayType):
            return (frame.push(stmts.FloatArrayLen(array)).result,)
        return (frame.push(stmts.IntArrayLen(array)).result,)


@py.indexing.dialect.register(key=KEY)
class _Indexing(interp.MethodTable):
    """A method table that reads an item of an array or a tuple."""

    @interp.impl(py.indexing.GetItem)
    def getitem(
        self, emit: Linearize, frame: Frame, stmt: py.indexing.GetItem
    ) -> interp.StatementResult[Value]:
        """Return the item, or None for a qubit, which its root names."""
        obj = frame.value(stmt.obj)
        if obj is None:
            return (None,)
        if isinstance(obj, ir.SSAValue):
            index = frame.scalar(stmt.index)
            if is_subtype(obj.type, FloatArrayType):
                return (frame.push(stmts.FloatArrayGet(obj, index)).result,)
            width = bitwidth(elements(stmt.obj.type).join(stmt.result.type))
            return (frame.push(stmts.IntArrayGet(obj, index, bitwidth=width)).result,)
        if (position := constant_int(stmt.index)) is not None:
            return (obj[position],)
        raise interp.InterpreterError(f"{stmt.obj} is not a tuple read at a constant")


@py.assign.dialect.register(key=KEY)
class _Assign(interp.MethodTable):
    """A method table that passes an alias through."""

    @interp.impl(py.assign.Alias)
    def alias(
        self, emit: Linearize, frame: Frame, stmt: py.assign.Alias
    ) -> interp.StatementResult[Value]:
        """Return the value of the aliased value."""
        return (frame.value(stmt.value),)
