"""Define statements that mirror jeff's integer, float and array operations.

A bit is jeff's 1-bit integer, which kirin types as `Bool`.
"""

from kirin import ir, types
from kirin.decl import info, statement

from bloqade.jeff.types import IntArrayType, FloatArrayType, is_bit

dialect = ir.Dialect("jeff.classical")

_pure = frozenset({ir.Pure()})
_constant = _pure | {ir.ConstantLike()}


def _check_fits(stmt: ir.Statement, value: object, bitwidth: object) -> None:
    """Raise a validation error if `value` is no integer of the positive `bitwidth`.

    A 1-bit value must be 0 or 1. A wider value must fit a two's complement
    pattern, so 8 bits hold -128 up to 127.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise ir.ValidationError(stmt, f"constant {value!r} is not an integer")
    if not isinstance(bitwidth, int) or bitwidth < 1:
        raise ir.ValidationError(stmt, f"bitwidth {bitwidth!r} is not positive")
    if bitwidth == 1:
        fits = value in (0, 1)
    else:
        bound = 1 << (bitwidth - 1)
        fits = -bound <= value < bound
    if not fits:
        raise ir.ValidationError(stmt, f"constant {value} does not fit {bitwidth} bits")


@statement(dialect=dialect)
class ConstInt(ir.Statement):
    """A statement that holds an integer constant of `bitwidth` bits.

    If the bitwidth is 1, the constant is a bit.
    """

    name = "const_int"

    traits = _constant
    value: int = info.attribute()
    bitwidth: int = info.attribute(default=32)
    result: ir.ResultValue = info.result(types.Int)

    def __init__(self, *, value: int, bitwidth: int = 32) -> None:
        """Build an integer constant that holds `value` in `bitwidth` bits."""
        super().__init__(
            result_types=(types.Bool if bitwidth == 1 else types.Int,),
            attributes={"value": ir.PyAttr(value), "bitwidth": ir.PyAttr(bitwidth)},
        )

    def verify(self) -> None:
        """Check that the value fits a positive bitwidth as a two's complement integer.

        If the bitwidth is 1, the value must be 0 or 1.
        """
        super().verify()
        _check_fits(self, self.value, self.bitwidth)
        if self.bitwidth == 1:
            fits = self.value in (0, 1)
        else:
            bound = 1 << (self.bitwidth - 1)
            fits = -bound <= self.value < bound
        if not fits:
            raise ir.ValidationError(
                self, f"constant {self.value} does not fit {self.bitwidth} bits"
            )

    def verify_type(self) -> None:
        """Check that the result is a bit exactly when the bitwidth is 1."""
        super().verify_type()
        if is_bit(self.result) != (self.bitwidth == 1):
            raise ir.TypeCheckError(
                self, f"a {self.bitwidth}-bit constant is typed {self.result.type}"
            )


@statement(dialect=dialect)
class ConstFloat(ir.Statement):
    """A statement that holds a float constant of `bitwidth` bits."""

    name = "const_float"

    traits = _constant
    value: float = info.attribute()
    bitwidth: int = info.attribute(default=64)
    result: ir.ResultValue = info.result(types.Float)

    def verify(self) -> None:
        """Check that the value is a number and that the bitwidth is 64."""
        super().verify()
        if not isinstance(self.value, (int, float)) or isinstance(self.value, bool):
            raise ir.ValidationError(self, f"constant {self.value!r} is not a number")
        if self.bitwidth != 64:
            raise ir.ValidationError(
                self,
                f"a float constant has bitwidth 64, and this one has {self.bitwidth!r}",
            )


def _bitwise(stmt: "IntBinary") -> None:
    """Check the operands and that the result has the same family as the operands."""
    IntBinary.verify_type(stmt)


@statement()
class IntBinary(ir.Statement):
    """A base statement that takes two integers and gives one integer."""

    traits = _pure
    lhs: ir.SSAValue = info.argument(types.Int)
    rhs: ir.SSAValue = info.argument(types.Int)
    result: ir.ResultValue = info.result(types.Int)

    def verify_type(self) -> None:
        """Check that the operands and the result are all bits or all integers."""
        super().verify_type()
        if is_bit(self.lhs) != is_bit(self.rhs):
            raise ir.TypeCheckError(
                self, "an integer operation mixes a bit with an integer"
            )
        if is_bit(self.lhs) != is_bit(self.result):
            operands, result = (
                ("bits", "a bit") if is_bit(self.lhs) else ("integers", "an integer")
            )
            raise ir.TypeCheckError(
                self, f"an operation on {operands} must give {result}"
            )


@statement()
class IntCompare(ir.Statement):
    """A base statement that compares two integers and gives a bit."""

    traits = _pure
    lhs: ir.SSAValue = info.argument(types.Int)
    rhs: ir.SSAValue = info.argument(types.Int)
    result: ir.ResultValue = info.result(types.Bool)

    def verify_type(self) -> None:
        """Check that both operands are bits or both operands are integers."""
        super().verify_type()
        if is_bit(self.lhs) != is_bit(self.rhs):
            raise ir.TypeCheckError(
                self, "an integer operation mixes a bit with an integer"
            )


@statement()
class IntUnary(ir.Statement):
    """A base statement that takes one integer and gives one integer."""

    traits = _pure
    value: ir.SSAValue = info.argument(types.Int)
    result: ir.ResultValue = info.result(types.Int)

    def verify_type(self) -> None:
        """Check that the result is a bit exactly when the operand is a bit."""
        super().verify_type()
        if is_bit(self.value) != is_bit(self.result):
            raise ir.TypeCheckError(
                self, f"'{self.name}' of a bit is a bit, of an integer an integer"
            )


@statement()
class FloatBinary(ir.Statement):
    """A base statement that takes two floats and gives one float."""

    traits = _pure
    lhs: ir.SSAValue = info.argument(types.Float)
    rhs: ir.SSAValue = info.argument(types.Float)
    result: ir.ResultValue = info.result(types.Float)


@statement()
class FloatCompare(ir.Statement):
    """A base statement that compares two floats and gives a bit."""

    traits = _pure
    lhs: ir.SSAValue = info.argument(types.Float)
    rhs: ir.SSAValue = info.argument(types.Float)
    result: ir.ResultValue = info.result(types.Bool)


@statement()
class FloatUnary(ir.Statement):
    """A base statement that takes one float and gives one float."""

    traits = _pure
    value: ir.SSAValue = info.argument(types.Float)
    result: ir.ResultValue = info.result(types.Float)


@statement()
class FloatPredicate(ir.Statement):
    """A base statement that tests one float and gives a bit."""

    traits = _pure
    value: ir.SSAValue = info.argument(types.Float)
    result: ir.ResultValue = info.result(types.Bool)


@statement(dialect=dialect)
class IntAdd(IntBinary):
    """A statement that adds two integers."""

    name = "int_add"


@statement(dialect=dialect)
class IntSub(IntBinary):
    """A statement that subtracts `rhs` from `lhs`."""

    name = "int_sub"


@statement(dialect=dialect)
class IntMul(IntBinary):
    """A statement that multiplies two integers."""

    name = "int_mul"


@statement(dialect=dialect)
class IntDivS(IntBinary):
    """A statement that divides `lhs` by `rhs` as signed integers.

    The quotient rounds toward zero, so -7 divided by 2 gives -3.
    """

    name = "int_div_s"


@statement(dialect=dialect)
class IntDivU(IntBinary):
    """A statement that divides `lhs` by `rhs` as unsigned integers."""

    name = "int_div_u"


@statement(dialect=dialect)
class IntPow(IntBinary):
    """A statement that raises `lhs` to the power `rhs`."""

    name = "int_pow"


@statement(dialect=dialect)
class IntAnd(IntBinary):
    """A statement that gives the bitwise and of two integers."""

    name = "int_and"

    def verify_type(self) -> None:
        """Check that the result is a bit exactly when the operands are bits."""
        _bitwise(self)


@statement(dialect=dialect)
class IntOr(IntBinary):
    """A statement that gives the bitwise or of two integers."""

    name = "int_or"

    def verify_type(self) -> None:
        """Check that the result is a bit exactly when the operands are bits."""
        _bitwise(self)


@statement(dialect=dialect)
class IntXor(IntBinary):
    """A statement that gives the bitwise exclusive or of two integers."""

    name = "int_xor"

    def verify_type(self) -> None:
        """Check that the result is a bit exactly when the operands are bits."""
        _bitwise(self)


@statement(dialect=dialect)
class IntMinS(IntBinary):
    """A statement that gives the smaller of two signed integers."""

    name = "int_min_s"


@statement(dialect=dialect)
class IntMinU(IntBinary):
    """A statement that gives the smaller of two unsigned integers."""

    name = "int_min_u"


@statement(dialect=dialect)
class IntMaxS(IntBinary):
    """A statement that gives the larger of two signed integers."""

    name = "int_max_s"


@statement(dialect=dialect)
class IntMaxU(IntBinary):
    """A statement that gives the larger of two unsigned integers."""

    name = "int_max_u"


@statement(dialect=dialect)
class IntRemS(IntBinary):
    """A statement that gives the remainder of signed integer division.

    The remainder takes the sign of `lhs`, so -7 and 2 give -1.
    """

    name = "int_rem_s"


@statement(dialect=dialect)
class IntRemU(IntBinary):
    """A statement that gives the remainder of unsigned integer division."""

    name = "int_rem_u"


@statement(dialect=dialect)
class IntShl(IntBinary):
    """A statement that shifts `lhs` left by `rhs` bits."""

    name = "int_shl"


@statement(dialect=dialect)
class IntShr(IntBinary):
    """A statement that shifts `lhs` right by `rhs` bits.

    The shift fills the high bits with zeros.
    """

    name = "int_shr"


@statement(dialect=dialect)
class IntEq(IntCompare):
    """A statement that checks whether two integers are equal."""

    name = "int_eq"


@statement(dialect=dialect)
class IntLtS(IntCompare):
    """A statement that checks whether `lhs` is less than `rhs` as signed integers."""

    name = "int_lt_s"


@statement(dialect=dialect)
class IntLteS(IntCompare):
    """A statement that checks whether `lhs` is at most `rhs` as signed integers."""

    name = "int_lte_s"


@statement(dialect=dialect)
class IntLtU(IntCompare):
    """A statement that checks whether `lhs` is less than `rhs` as unsigned integers."""

    name = "int_lt_u"


@statement(dialect=dialect)
class IntLteU(IntCompare):
    """A statement that checks whether `lhs` is at most `rhs` as unsigned integers."""

    name = "int_lte_u"


@statement(dialect=dialect)
class IntNot(IntUnary):
    """A statement that flips every bit of an integer."""

    name = "int_not"


@statement(dialect=dialect)
class IntAbs(IntUnary):
    """A statement that gives the absolute value of a signed integer."""

    name = "int_abs"


@statement(dialect=dialect)
class IntSelect(ir.Statement):
    """A statement that gives `yes` if `condition` is 1 and gives `no` otherwise."""

    name = "int_select"
    traits = _pure
    condition: ir.SSAValue = info.argument(types.Bool)
    yes: ir.SSAValue = info.argument(types.Int)
    no: ir.SSAValue = info.argument(types.Int)
    result: ir.ResultValue = info.result(types.Int)

    def verify_type(self) -> None:
        """Check that both choices and the result are all bits or all integers."""
        super().verify_type()
        if len({is_bit(self.yes), is_bit(self.no), is_bit(self.result)}) != 1:
            raise ir.TypeCheckError(
                self, "a select must choose between two bits or two integers"
            )


@statement(dialect=dialect)
class FloatSelect(ir.Statement):
    """A statement that gives `yes` if `condition` is 1 and gives `no` otherwise."""

    name = "float_select"
    traits = _pure
    condition: ir.SSAValue = info.argument(types.Bool)
    yes: ir.SSAValue = info.argument(types.Float)
    no: ir.SSAValue = info.argument(types.Float)
    result: ir.ResultValue = info.result(types.Float)


@statement(dialect=dialect)
class FloatAdd(FloatBinary):
    """A statement that adds two floats."""

    name = "float_add"


@statement(dialect=dialect)
class FloatSub(FloatBinary):
    """A statement that subtracts `rhs` from `lhs`."""

    name = "float_sub"


@statement(dialect=dialect)
class FloatMul(FloatBinary):
    """A statement that multiplies two floats."""

    name = "float_mul"


@statement(dialect=dialect)
class FloatPow(FloatBinary):
    """A statement that raises `lhs` to the power `rhs`."""

    name = "float_pow"


@statement(dialect=dialect)
class FloatAtan2(FloatBinary):
    """A statement that gives the arctangent of `lhs` divided by `rhs`.

    The statement uses the signs of both operands to pick the quadrant.
    """

    name = "float_atan2"


@statement(dialect=dialect)
class FloatMax(FloatBinary):
    """A statement that gives the larger of two floats."""

    name = "float_max"


@statement(dialect=dialect)
class FloatMin(FloatBinary):
    """A statement that gives the smaller of two floats."""

    name = "float_min"


@statement(dialect=dialect)
class FloatEq(FloatCompare):
    """A statement that checks whether two floats are equal."""

    name = "float_eq"


@statement(dialect=dialect)
class FloatLt(FloatCompare):
    """A statement that checks whether `lhs` is less than `rhs`."""

    name = "float_lt"


@statement(dialect=dialect)
class FloatLte(FloatCompare):
    """A statement that checks whether `lhs` is at most `rhs`."""

    name = "float_lte"


@statement(dialect=dialect)
class FloatSqrt(FloatUnary):
    """A statement that gives the square root of a float."""

    name = "float_sqrt"


@statement(dialect=dialect)
class FloatAbs(FloatUnary):
    """A statement that gives the absolute value of a float."""

    name = "float_abs"


@statement(dialect=dialect)
class FloatCeil(FloatUnary):
    """A statement that rounds a float up to the nearest whole number."""

    name = "float_ceil"


@statement(dialect=dialect)
class FloatFloor(FloatUnary):
    """A statement that rounds a float down to the nearest whole number."""

    name = "float_floor"


@statement(dialect=dialect)
class FloatExp(FloatUnary):
    """A statement that raises e to the power of a float."""

    name = "float_exp"


@statement(dialect=dialect)
class FloatLog(FloatUnary):
    """A statement that gives the natural logarithm of a float."""

    name = "float_log"


@statement(dialect=dialect)
class FloatSin(FloatUnary):
    """A statement that gives the sine of a float."""

    name = "float_sin"


@statement(dialect=dialect)
class FloatCos(FloatUnary):
    """A statement that gives the cosine of a float."""

    name = "float_cos"


@statement(dialect=dialect)
class FloatTan(FloatUnary):
    """A statement that gives the tangent of a float."""

    name = "float_tan"


@statement(dialect=dialect)
class FloatAsin(FloatUnary):
    """A statement that gives the arcsine of a float."""

    name = "float_asin"


@statement(dialect=dialect)
class FloatAcos(FloatUnary):
    """A statement that gives the arccosine of a float."""

    name = "float_acos"


@statement(dialect=dialect)
class FloatAtan(FloatUnary):
    """A statement that gives the arctangent of a float."""

    name = "float_atan"


@statement(dialect=dialect)
class FloatSinh(FloatUnary):
    """A statement that gives the hyperbolic sine of a float."""

    name = "float_sinh"


@statement(dialect=dialect)
class FloatCosh(FloatUnary):
    """A statement that gives the hyperbolic cosine of a float."""

    name = "float_cosh"


@statement(dialect=dialect)
class FloatTanh(FloatUnary):
    """A statement that gives the hyperbolic tangent of a float."""

    name = "float_tanh"


@statement(dialect=dialect)
class FloatAsinh(FloatUnary):
    """A statement that gives the inverse hyperbolic sine of a float."""

    name = "float_asinh"


@statement(dialect=dialect)
class FloatAcosh(FloatUnary):
    """A statement that gives the inverse hyperbolic cosine of a float."""

    name = "float_acosh"


@statement(dialect=dialect)
class FloatAtanh(FloatUnary):
    """A statement that gives the inverse hyperbolic tangent of a float."""

    name = "float_atanh"


@statement(dialect=dialect)
class FloatIsNan(FloatPredicate):
    """A statement that checks whether a float is NaN."""

    name = "float_is_nan"


@statement(dialect=dialect)
class FloatIsInf(FloatPredicate):
    """A statement that checks whether a float is infinite."""

    name = "float_is_inf"


@statement(dialect=dialect)
class IntArrayConst(ir.Statement):
    """A statement that holds a constant integer array of `bitwidth`-bit elements."""

    name = "int_array_const"

    traits = _pure
    values: tuple[int, ...] = info.attribute()
    bitwidth: int = info.attribute(default=32)
    result: ir.ResultValue = info.result(IntArrayType)

    def verify(self) -> None:
        """Check that each value is an integer that fits the positive bitwidth."""
        super().verify()
        for value in self.values:
            _check_fits(self, value, self.bitwidth)


@statement(dialect=dialect)
class IntArrayZero(ir.Statement):
    """A statement that builds an integer array of `size` zeros.

    The length `size` is a runtime value.
    """

    name = "int_array_zero"

    traits = _pure
    size: ir.SSAValue = info.argument(types.Int)
    bitwidth: int = info.attribute(default=1)
    result: ir.ResultValue = info.result(IntArrayType)


@statement(dialect=dialect)
class IntArrayGet(ir.Statement):
    """A statement that reads the element of an integer array at an index.

    If `bitwidth` is 1, the element is a bit.
    """

    name = "int_array_get"

    traits = _pure
    array: ir.SSAValue = info.argument(IntArrayType)
    index: ir.SSAValue = info.argument(types.Int)
    bitwidth: int = info.attribute(default=1)
    result: ir.ResultValue = info.result(types.Int)

    def __init__(
        self, array: ir.SSAValue, index: ir.SSAValue, *, bitwidth: int = 1
    ) -> None:
        """Build a read of `array` at `index` that gives a `bitwidth`-bit integer."""
        super().__init__(
            args=(array, index),
            result_types=(types.Bool if bitwidth == 1 else types.Int,),
            args_slice={"array": 0, "index": 1},
            attributes={"bitwidth": ir.PyAttr(bitwidth)},
        )

    def verify_type(self) -> None:
        """Check that the result is a bit exactly when the bitwidth is 1."""
        super().verify_type()
        if is_bit(self.result) != (self.bitwidth == 1):
            raise ir.TypeCheckError(
                self, f"a {self.bitwidth}-bit element is typed {self.result.type}"
            )


@statement(dialect=dialect)
class IntArraySet(ir.Statement):
    """A statement that gives a copy of `array` with `value` at `index`."""

    name = "int_array_set"

    traits = _pure
    array: ir.SSAValue = info.argument(IntArrayType)
    index: ir.SSAValue = info.argument(types.Int)
    value: ir.SSAValue = info.argument(types.Int)
    result: ir.ResultValue = info.result(IntArrayType)


@statement(dialect=dialect)
class IntArrayLen(ir.Statement):
    """A statement that gives the length of an integer array."""

    name = "int_array_len"

    traits = _pure
    array: ir.SSAValue = info.argument(IntArrayType)
    result: ir.ResultValue = info.result(types.Int)


@statement(dialect=dialect, init=False)
class IntArrayCreate(ir.Statement):
    """A statement that builds an integer array from separate integer values."""

    name = "int_array_create"

    traits = _pure
    values: tuple[ir.SSAValue, ...] = info.argument(types.Int)
    bitwidth: int = info.attribute(default=32)
    result: ir.ResultValue = info.result(IntArrayType)

    def __init__(self, values: tuple[ir.SSAValue, ...], *, bitwidth: int = 32) -> None:
        """Build an integer array of `bitwidth`-bit elements from `values`."""
        super().__init__(
            args=values,
            result_types=(IntArrayType,),
            args_slice={"values": slice(0, None)},
            attributes={"bitwidth": ir.PyAttr(bitwidth)},
        )

    def verify_type(self) -> None:
        """Check that each value is a bit exactly when the bitwidth is 1."""
        super().verify_type()
        for value in self.values:
            if is_bit(value) != (self.bitwidth == 1):
                raise ir.TypeCheckError(
                    self,
                    f"a {self.bitwidth}-bit array takes a value typed {value.type}",
                )


@statement(dialect=dialect)
class FloatArrayConst(ir.Statement):
    """A statement that holds a constant float array."""

    name = "float_array_const"

    traits = _pure
    values: tuple[float, ...] = info.attribute()
    result: ir.ResultValue = info.result(FloatArrayType)


@statement(dialect=dialect)
class FloatArrayZero(ir.Statement):
    """A statement that builds a float array of `size` zeros.

    The length `size` is a runtime value.
    """

    name = "float_array_zero"

    traits = _pure
    size: ir.SSAValue = info.argument(types.Int)
    result: ir.ResultValue = info.result(FloatArrayType)


@statement(dialect=dialect)
class FloatArrayGet(ir.Statement):
    """A statement that reads the element of a float array at an index."""

    name = "float_array_get"

    traits = _pure
    array: ir.SSAValue = info.argument(FloatArrayType)
    index: ir.SSAValue = info.argument(types.Int)
    result: ir.ResultValue = info.result(types.Float)


@statement(dialect=dialect)
class FloatArraySet(ir.Statement):
    """A statement that gives a copy of `array` with `value` at `index`."""

    name = "float_array_set"

    traits = _pure
    array: ir.SSAValue = info.argument(FloatArrayType)
    index: ir.SSAValue = info.argument(types.Int)
    value: ir.SSAValue = info.argument(types.Float)
    result: ir.ResultValue = info.result(FloatArrayType)


@statement(dialect=dialect)
class FloatArrayLen(ir.Statement):
    """A statement that gives the length of a float array."""

    name = "float_array_len"

    traits = _pure
    array: ir.SSAValue = info.argument(FloatArrayType)
    result: ir.ResultValue = info.result(types.Int)


@statement(dialect=dialect, init=False)
class FloatArrayCreate(ir.Statement):
    """A statement that builds a float array from separate float values."""

    name = "float_array_create"

    traits = _pure
    values: tuple[ir.SSAValue, ...] = info.argument(types.Float)
    result: ir.ResultValue = info.result(FloatArrayType)

    def __init__(self, values: tuple[ir.SSAValue, ...]) -> None:
        """Build a float array from `values`."""
        super().__init__(
            args=values,
            result_types=(FloatArrayType,),
            args_slice={"values": slice(0, None)},
        )
