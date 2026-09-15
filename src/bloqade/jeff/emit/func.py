"""This module holds the emission of each kirin function as a jeff function."""

from functools import partial
from collections.abc import Callable

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

_SCALAR_TYPES: dict[types.TypeAttribute, Callable[[], JeffType]] = {
    WireType: QubitType,
    IntArrayType: partial(JeffIntArrayType, 1),
    FloatArrayType: partial(JeffFloatArrayType, 64),
    types.Bool: partial(IntType, 1),
    types.Int: partial(IntType, 32),
    types.Float: partial(FloatType, 64),
}
"""The constructor of the jeff type for each kirin type without parameters."""


def jeff_type(kirin_type: types.TypeAttribute) -> JeffType:
    """Return the jeff type of a value at a function boundary.

    The function raises InterpreterError if the kirin type has no jeff type.
    """
    if is_subtype(kirin_type, QuregType):
        return JeffQuregType(qureg_length(kirin_type))
    make = _SCALAR_TYPES.get(kirin_type)
    if make is None:
        raise interp.exceptions.InterpreterError(
            f"The type {kirin_type} has no jeff form at a function boundary."
        )
    return make()


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
