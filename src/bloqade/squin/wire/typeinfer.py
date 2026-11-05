"""Infer the static length of wire registers with Kirin's type inference.

A register type carries its number of qubits when it is known, such as `Register[3]`
for `AllocRegister(3)`. A statement that continues a register keeps the type of its
input, and Kirin joins the types of loop and branch state.
"""

from typing import TypeAlias

from kirin import types, interp
from kirin.passes import TypeInfer as TypeInferPass
from kirin.dialects import func
from kirin.analysis.forward import ForwardFrame
from kirin.analysis.typeinfer import TypeInference
from kirin.dialects.func.typeinfer import TypeInfer as FunctionTypes

from . import stmts
from .types import WireType, register_type, register_length
from ._dialect import dialect
from .ownership import inout_result_type

Frame: TypeAlias = ForwardFrame[types.TypeAttribute]
"""Name the frame of Kirin's type inference."""


@func.dialect.register(key="typeinfer.squin_wire")
class InOutCalls(interp.MethodTable):
    """Infer call results with the register lengths that in-out functions preserve."""

    @interp.impl(func.Invoke)
    def invoke(
        self, infer: TypeInference, frame: Frame, stmt: func.Invoke
    ) -> tuple[types.TypeAttribute]:
        """Keep ordinary result types and copy quantum argument types into the return suffix."""
        outputs = FunctionTypes().invoke(infer, frame, stmt)
        assert isinstance(outputs, tuple) and len(outputs) == 1
        result = outputs[0]
        code = stmt.callee.code
        if isinstance(code, func.Function):
            result = inout_result_type(code, result, frame.get_values(stmt.inputs))
        return (result,)


class InferWireTypes(TypeInferPass):
    """Run Kirin type inference with the in-out convention of wire functions."""

    def __post_init__(self) -> None:
        """Select the wire call rule before Kirin's general function rules."""
        super().__post_init__()
        self.infer.registry = self.dialects.registry.interpreter(
            keys=("typeinfer.squin_wire", *self.infer.keys)
        )


@dialect.register(key="typeinfer")
class TypeInfer(interp.MethodTable):
    """Give each register result the static length that its operands imply."""

    @interp.impl(stmts.AllocRegister)
    def alloc(
        self, infer: TypeInference, frame: Frame, stmt: stmts.AllocRegister
    ) -> tuple[types.TypeAttribute, ...]:
        """Type the register of a constant size with that size."""
        return (register_type(infer.maybe_const(stmt.size, int)),)

    @interp.impl(stmts.PackRegister)
    def pack(
        self, infer: TypeInference, frame: Frame, stmt: stmts.PackRegister
    ) -> tuple[types.TypeAttribute, ...]:
        """Type the register with the number of packed wires."""
        return (register_type(len(stmt.wires)),)

    @interp.impl(stmts.Borrow)
    @interp.impl(stmts.Take)
    def borrow(
        self, infer: TypeInference, frame: Frame, stmt: stmts.Borrow | stmts.Take
    ) -> tuple[types.TypeAttribute, ...]:
        """Keep the register type and return a wire."""
        return frame.get(stmt.register), WireType

    @interp.impl(stmts.Release)
    @interp.impl(stmts.Put)
    @interp.impl(stmts.PutSlice)
    def release(
        self,
        infer: TypeInference,
        frame: Frame,
        stmt: stmts.Release | stmts.Put | stmts.PutSlice,
    ) -> tuple[types.TypeAttribute, ...]:
        """Keep the register type."""
        return (frame.get(stmt.register),)

    @interp.impl(stmts.Length)
    def length(
        self, infer: TypeInference, frame: Frame, stmt: stmts.Length
    ) -> tuple[types.TypeAttribute, ...]:
        """Keep the register type and return an integer."""
        return frame.get(stmt.register), types.Int

    @interp.impl(stmts.TakeSlice)
    def take_slice(
        self, infer: TypeInference, frame: Frame, stmt: stmts.TakeSlice
    ) -> tuple[types.TypeAttribute, ...]:
        """Keep the register type and type the slice with a constant length."""
        size = register_type(infer.maybe_const(stmt.length, int))
        return frame.get(stmt.register), size

    @interp.impl(stmts.SplitRegister)
    def split(
        self, infer: TypeInference, frame: Frame, stmt: stmts.SplitRegister
    ) -> tuple[types.TypeAttribute, ...]:
        """Type both parts when the length and the split index are known."""
        total = register_length(frame.get(stmt.register))
        at = infer.maybe_const(stmt.index, int)
        rest = None if total is None or at is None else total - at
        if (at is not None and at < 0) or (rest is not None and rest < 0):
            return types.Bottom, types.Bottom
        return register_type(at), register_type(rest)

    @interp.impl(stmts.JoinRegister)
    def join(
        self, infer: TypeInference, frame: Frame, stmt: stmts.JoinRegister
    ) -> tuple[types.TypeAttribute, ...]:
        """Type the joined register with the sum of both known lengths."""
        a = register_length(frame.get(stmt.first))
        b = register_length(frame.get(stmt.second))
        return (register_type(None if a is None or b is None else a + b),)

    @interp.impl(stmts.RegisterGate)
    @interp.impl(stmts.RegisterNoise)
    @interp.impl(stmts.RegisterMeasure)
    @interp.impl(stmts.RegisterReset)
    def register_operation(
        self, infer: TypeInference, frame: Frame, stmt: stmts.RegisterOperation
    ) -> tuple[types.TypeAttribute, ...]:
        """Keep each register operand type and each classical result type."""
        registers = tuple(frame.get(register) for register in stmt.linear)
        return registers + tuple(result.type for result in stmt.classical)
