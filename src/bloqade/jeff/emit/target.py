"""This module holds the entry point that emits a jeff program as a jeff module."""

from importlib.metadata import version

from kirin import ir

from jeff import JeffFunc, JeffModule
from bloqade.jeff.dialects import kernel as jeff_kernel
from bloqade.jeff.emit.base import EmitJeff


def emit_jeff(method: ir.Method) -> JeffModule:
    """Emit a jeff program and every function that it calls as one jeff module."""
    if not isinstance(method, ir.Method) or method.dialects is not jeff_kernel:
        raise TypeError(
            "emit_jeff takes a jeff program in the `jeff.kernel` dialect group."
        )
    if method.callable_region.blocks[0].first_stmt is None:
        raise TypeError("The program's body is empty.")
    emitter = EmitJeff(dialects=jeff_kernel)
    emitter.run(method.code)
    functions: list[JeffFunc] = list(emitter.function_defs)
    module = JeffModule(
        functions,
        entrypoint=0,
        tool="bloqade-circuit",
        tool_version=version("bloqade-circuit"),
    )
    module.refresh()
    return module
