"""This module holds the emission of the `jeff.func` statements."""

from kirin import interp

from jeff import JeffOp, JeffValue
from bloqade.jeff.dialects import stmts

from .base import EmitJeff, JeffFrame
from .func import jeff_type


@stmts.call.dialect.register(key="emit.jeff")
class _Call(interp.MethodTable):
    """Emit the `jeff.func` statements."""

    @interp.impl(stmts.Call)
    def call(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.Call
    ) -> tuple[JeffValue, ...]:
        """Emit a function call and queue the callee when the emitter first sees it."""
        callee = stmt.callee.code
        if callee not in emit.function_index:
            emit.function_index[callee] = len(emit.function_index)
            emit.callable_to_emit.append(callee)
        index = emit.function_index[callee]
        outputs = [JeffValue(jeff_type(result.type)) for result in stmt.results]
        frame.push(
            JeffOp(
                "func",
                "funcCall",
                [frame.get(value) for value in stmt.inputs],
                outputs,
                instruction_data=index,
            )
        )
        return tuple(outputs)

    @interp.impl(stmts.Return)
    def return_(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.Return
    ) -> interp.ReturnValue[tuple[JeffValue, ...]]:
        """End the function with the values that it returns."""
        return interp.ReturnValue(frame.get_values(stmt.values))
