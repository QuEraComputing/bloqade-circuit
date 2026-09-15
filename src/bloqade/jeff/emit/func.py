"""This module holds the emission of each kirin function as a jeff function."""

from kirin import types, interp
from kirin.dialects import func, ssacfg

from jeff import (
    IntType,
    JeffType,
    FloatType,
    JeffValue,
    QubitType,
    QuregType as JeffQuregType,
    JeffRegion,
    FunctionDef,
    IntArrayType as JeffIntArrayType,
    FloatArrayType as JeffFloatArrayType,
)
from bloqade.jeff.types import (
    WireType,
    QuregType,
    IntArrayType,
    FloatArrayType,
    is_subtype,
    qureg_length,
)

from .base import EmitJeff, JeffFrame


def jeff_type(kirin_type: types.TypeAttribute) -> JeffType:
    """Return the jeff type of a value at a function boundary.

    The function raises InterpreterError if the kirin type has no jeff type.
    """
    if is_subtype(kirin_type, WireType):
        return QubitType()
    if is_subtype(kirin_type, QuregType):
        return JeffQuregType(qureg_length(kirin_type))
    if is_subtype(kirin_type, IntArrayType):
        return JeffIntArrayType(1)
    if is_subtype(kirin_type, FloatArrayType):
        return JeffFloatArrayType(64)
    if is_subtype(kirin_type, types.Bool):
        return IntType(1)
    if is_subtype(kirin_type, types.Int):
        return IntType(32)
    if is_subtype(kirin_type, types.Float):
        return FloatType(64)
    raise interp.exceptions.InterpreterError(
        f"The type {kirin_type} has no jeff form at a function boundary."
    )


@func.dialect.register(key="emit.jeff")
class _Func(interp.MethodTable):
    """Emit the kirin `func` statements."""

    @interp.impl(func.Function)
    def function(
        self, emit: EmitJeff, frame: JeffFrame, stmt: func.Function
    ) -> tuple[()]:
        """Emit the function body as a jeff function."""
        emit.function_index.setdefault(stmt, len(emit.function_index))
        sources = [
            JeffValue(jeff_type(arg.type)) for arg in stmt.body.blocks[0].args[1:]
        ]
        returned = emit.frame_call(frame, stmt, emit.void, *sources)
        if not isinstance(returned, tuple):
            raise interp.exceptions.InterpreterError(
                f"The function {stmt.sym_name} does not end in a return."
            )
        targets = list(returned)
        body = JeffRegion(sources=sources, targets=targets, operations=frame.operations)
        emit.function_defs.append(FunctionDef(name=stmt.sym_name, body=body))
        return ()


@ssacfg.dialect.register(key="emit.jeff")
class _SsaCfg(ssacfg.Concrete):
    """Run the statements of an SSA control-flow region with kirin's concrete rule."""
