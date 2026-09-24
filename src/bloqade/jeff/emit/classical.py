"""This module holds the emission of the `jeff.classical` statements."""

from kirin import interp

from jeff import (
    JeffOp,
    IntType,
    FloatType,
    JeffValue,
    SwitchSCF,
    JeffRegion,
    IntArrayType,
    FloatArrayType,
)
from bloqade.constants import constant_int
from bloqade.jeff.names import subkind
from bloqade.jeff.dialects import stmts

from .base import EmitJeff, JeffFrame


def _pattern(value: int, bitwidth: int) -> int:
    """Return the two's complement bit pattern of `value` in `bitwidth` bits.

    The function raises ValueError if `value` does not fit `bitwidth` bits.
    """
    bound = 1 << (bitwidth - 1)
    if not -bound <= value < bound:
        raise ValueError(f"The integer constant {value} does not fit {bitwidth} bits.")
    return value & ((1 << bitwidth) - 1)


@stmts.classical.dialect.register(key="emit.jeff")
class _Classical(interp.MethodTable):
    """Emit the `jeff.classical` statements."""

    @interp.impl(stmts.ConstInt)
    def constant_int(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.ConstInt
    ) -> tuple[JeffValue, ...]:
        """Emit an integer constant."""
        value = (
            bool(stmt.value)
            if stmt.bitwidth == 1
            else _pattern(stmt.value, stmt.bitwidth)
        )
        op = frame.push(
            JeffOp(
                "int",
                f"const{stmt.bitwidth}",
                [],
                [JeffValue(IntType(stmt.bitwidth))],
                instruction_data=value,
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.ConstFloat)
    def const_float(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.ConstFloat
    ) -> tuple[JeffValue, ...]:
        """Emit a float constant."""
        op = frame.push(
            JeffOp(
                "float",
                f"const{stmt.bitwidth}",
                [],
                [JeffValue(FloatType(stmt.bitwidth))],
                instruction_data=stmt.value,
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.IntAdd)
    @interp.impl(stmts.IntSub)
    @interp.impl(stmts.IntMul)
    @interp.impl(stmts.IntDivS)
    @interp.impl(stmts.IntDivU)
    @interp.impl(stmts.IntPow)
    @interp.impl(stmts.IntAnd)
    @interp.impl(stmts.IntOr)
    @interp.impl(stmts.IntXor)
    @interp.impl(stmts.IntMinS)
    @interp.impl(stmts.IntMinU)
    @interp.impl(stmts.IntMaxS)
    @interp.impl(stmts.IntMaxU)
    @interp.impl(stmts.IntRemS)
    @interp.impl(stmts.IntRemU)
    @interp.impl(stmts.IntShl)
    @interp.impl(stmts.IntShr)
    def int_binary(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.IntBinary
    ) -> tuple[JeffValue, ...]:
        """Emit a binary integer operation."""
        lhs = frame.get(stmt.lhs)
        op = frame.push(
            JeffOp(
                "int",
                subkind(stmt.name, "int_"),
                [lhs, frame.get(stmt.rhs)],
                [JeffValue(lhs.type)],
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.IntEq)
    @interp.impl(stmts.IntLtS)
    @interp.impl(stmts.IntLteS)
    @interp.impl(stmts.IntLtU)
    @interp.impl(stmts.IntLteU)
    def int_compare(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.IntCompare
    ) -> tuple[JeffValue, ...]:
        """Emit an integer comparison."""
        op = frame.push(
            JeffOp(
                "int",
                subkind(stmt.name, "int_"),
                [frame.get(stmt.lhs), frame.get(stmt.rhs)],
                [JeffValue(IntType(1))],
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.IntNot)
    @interp.impl(stmts.IntAbs)
    def int_unary(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.IntUnary
    ) -> tuple[JeffValue, ...]:
        """Emit a unary integer operation."""
        value = frame.get(stmt.value)
        op = frame.push(
            JeffOp(
                "int",
                subkind(stmt.name, "int_"),
                [value],
                [JeffValue(value.type)],
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.IntSelect)
    @interp.impl(stmts.FloatSelect)
    def select(
        self,
        emit: EmitJeff,
        frame: JeffFrame,
        stmt: stmts.IntSelect | stmts.FloatSelect,
    ) -> tuple[JeffValue, ...]:
        """Emit a select as a switch on its condition."""
        condition, yes, no = (
            frame.get(value) for value in (stmt.condition, stmt.yes, stmt.no)
        )

        def picking(position: int) -> JeffRegion:
            """Return a region that yields the input at `position`."""
            sources = [JeffValue(yes.type), JeffValue(no.type)]
            return JeffRegion(
                sources=sources, targets=[sources[position]], operations=[]
            )

        op = frame.push(
            JeffOp(
                "scf",
                "switch",
                [condition, yes, no],
                [JeffValue(yes.type)],
                instruction_data=SwitchSCF(branches=[picking(1)], default=picking(0)),
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.FloatAdd)
    @interp.impl(stmts.FloatSub)
    @interp.impl(stmts.FloatMul)
    @interp.impl(stmts.FloatPow)
    @interp.impl(stmts.FloatAtan2)
    @interp.impl(stmts.FloatMax)
    @interp.impl(stmts.FloatMin)
    def float_binary(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.FloatBinary
    ) -> tuple[JeffValue, ...]:
        """Emit a binary float operation."""
        lhs = frame.get(stmt.lhs)
        op = frame.push(
            JeffOp(
                "float",
                subkind(stmt.name, "float_"),
                [lhs, frame.get(stmt.rhs)],
                [JeffValue(lhs.type)],
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.FloatEq)
    @interp.impl(stmts.FloatLt)
    @interp.impl(stmts.FloatLte)
    def float_compare(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.FloatCompare
    ) -> tuple[JeffValue, ...]:
        """Emit a float comparison."""
        op = frame.push(
            JeffOp(
                "float",
                subkind(stmt.name, "float_"),
                [frame.get(stmt.lhs), frame.get(stmt.rhs)],
                [JeffValue(IntType(1))],
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.FloatSqrt)
    @interp.impl(stmts.FloatAbs)
    @interp.impl(stmts.FloatCeil)
    @interp.impl(stmts.FloatFloor)
    @interp.impl(stmts.FloatExp)
    @interp.impl(stmts.FloatLog)
    @interp.impl(stmts.FloatSin)
    @interp.impl(stmts.FloatCos)
    @interp.impl(stmts.FloatTan)
    @interp.impl(stmts.FloatAsin)
    @interp.impl(stmts.FloatAcos)
    @interp.impl(stmts.FloatAtan)
    @interp.impl(stmts.FloatSinh)
    @interp.impl(stmts.FloatCosh)
    @interp.impl(stmts.FloatTanh)
    @interp.impl(stmts.FloatAsinh)
    @interp.impl(stmts.FloatAcosh)
    @interp.impl(stmts.FloatAtanh)
    def float_unary(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.FloatUnary
    ) -> tuple[JeffValue, ...]:
        """Emit a unary float operation."""
        value = frame.get(stmt.value)
        op = frame.push(
            JeffOp(
                "float",
                subkind(stmt.name, "float_"),
                [value],
                [JeffValue(value.type)],
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.FloatIsNan)
    @interp.impl(stmts.FloatIsInf)
    def float_predicate(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.FloatPredicate
    ) -> tuple[JeffValue, ...]:
        """Emit a float predicate."""
        op = frame.push(
            JeffOp(
                "float",
                subkind(stmt.name, "float_"),
                [frame.get(stmt.value)],
                [JeffValue(IntType(1))],
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.IntArrayConst)
    def int_array_const(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.IntArrayConst
    ) -> tuple[JeffValue, ...]:
        """Emit an integer array constant."""
        op = frame.push(
            JeffOp(
                "intArray",
                f"const{stmt.bitwidth}",
                [],
                [JeffValue(IntArrayType(stmt.bitwidth, len(stmt.values)))],
                instruction_data=(
                    [bool(v) for v in stmt.values]
                    if stmt.bitwidth == 1
                    else [_pattern(v, stmt.bitwidth) for v in stmt.values]
                ),
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.IntArrayZero)
    def int_array_zero(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.IntArrayZero
    ) -> tuple[JeffValue, ...]:
        """Emit an integer array that holds zeros."""
        length = constant_int(stmt.size)
        op = frame.push(
            JeffOp(
                "intArray",
                "zero",
                [frame.get(stmt.size)],
                [JeffValue(IntArrayType(stmt.bitwidth, length))],
                instruction_data=stmt.bitwidth,
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.IntArrayGet)
    def int_array_get(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.IntArrayGet
    ) -> tuple[JeffValue, ...]:
        """Emit a read from an integer array."""
        op = frame.push(
            JeffOp(
                "intArray",
                "getIndex",
                [frame.get(stmt.array), frame.get(stmt.index)],
                [JeffValue(IntType(stmt.bitwidth))],
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.IntArraySet)
    def int_array_set(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.IntArraySet
    ) -> tuple[JeffValue, ...]:
        """Emit a write to an integer array."""
        array = frame.get(stmt.array)
        op = frame.push(
            JeffOp(
                "intArray",
                "setIndex",
                [array, frame.get(stmt.index), frame.get(stmt.value)],
                [JeffValue(array.type)],
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.IntArrayLen)
    def int_array_len(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.IntArrayLen
    ) -> tuple[JeffValue, ...]:
        """Emit a query of the integer array length."""
        op = frame.push(
            JeffOp(
                "intArray",
                "length",
                [frame.get(stmt.array)],
                [JeffValue(IntType(32))],
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.IntArrayCreate)
    def int_array_create(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.IntArrayCreate
    ) -> tuple[JeffValue, ...]:
        """Emit an integer array built from integers."""
        values = [frame.get(value) for value in stmt.values]
        op = frame.push(
            JeffOp(
                "intArray",
                "create",
                values,
                [JeffValue(IntArrayType(stmt.bitwidth, len(values)))],
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.FloatArrayConst)
    def float_array_const(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.FloatArrayConst
    ) -> tuple[JeffValue, ...]:
        """Emit a float array constant."""
        op = frame.push(
            JeffOp(
                "floatArray",
                "const64",
                [],
                [JeffValue(FloatArrayType(64, len(stmt.values)))],
                instruction_data=list(stmt.values),
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.FloatArrayZero)
    def float_array_zero(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.FloatArrayZero
    ) -> tuple[JeffValue, ...]:
        """Emit a float array that holds zeros."""
        op = frame.push(
            JeffOp(
                "floatArray",
                "zero",
                [frame.get(stmt.size)],
                [JeffValue(FloatArrayType(64))],
                instruction_data=64,
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.FloatArrayGet)
    def float_array_get(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.FloatArrayGet
    ) -> tuple[JeffValue, ...]:
        """Emit a read from a float array."""
        op = frame.push(
            JeffOp(
                "floatArray",
                "getIndex",
                [frame.get(stmt.array), frame.get(stmt.index)],
                [JeffValue(FloatType(64))],
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.FloatArraySet)
    def float_array_set(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.FloatArraySet
    ) -> tuple[JeffValue, ...]:
        """Emit a write to a float array."""
        array = frame.get(stmt.array)
        op = frame.push(
            JeffOp(
                "floatArray",
                "setIndex",
                [array, frame.get(stmt.index), frame.get(stmt.value)],
                [JeffValue(array.type)],
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.FloatArrayLen)
    def float_array_len(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.FloatArrayLen
    ) -> tuple[JeffValue, ...]:
        """Emit a query of the float array length."""
        op = frame.push(
            JeffOp(
                "floatArray",
                "length",
                [frame.get(stmt.array)],
                [JeffValue(IntType(32))],
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.FloatArrayCreate)
    def float_array_create(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.FloatArrayCreate
    ) -> tuple[JeffValue, ...]:
        """Emit a float array built from floats."""
        values = [frame.get(value) for value in stmt.values]
        op = frame.push(
            JeffOp(
                "floatArray",
                "create",
                values,
                [JeffValue(FloatArrayType(64, len(values)))],
            )
        )
        return (op.outputs[0],)
