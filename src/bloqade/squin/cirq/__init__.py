from typing import Any

import cirq
from kirin import ir, types
from kirin.dialects import func

from . import lowering as lowering
from .. import kernel
from .lowering import Squin


def load_circuit(
    circuit: cirq.Circuit,
    kernel_name: str = "main",
    dialects: ir.DialectGroup = kernel,
    globals: dict[str, Any] | None = None,
    file: str | None = None,
    lineno_offset: int = 0,
    col_offset: int = 0,
    compactify: bool = True,
):

    target = Squin(dialects=dialects, circuit=circuit)
    body = target.run(
        circuit,
        source=str(circuit),  # TODO: proper source string
        file=file,
        globals=globals,
        lineno_offset=lineno_offset,
        col_offset=col_offset,
        compactify=compactify,
    )

    # NOTE: no return value
    return_value = func.ConstantNone()
    body.blocks[0].stmts.append(return_value)
    body.blocks[0].stmts.append(func.Return(value_or_stmt=return_value))

    code = func.Function(
        sym_name=kernel_name,
        signature=func.Signature((), types.NoneType),
        body=body,
    )

    return ir.Method(
        mod=None,
        py_func=None,
        sym_name=kernel_name,
        arg_names=[],
        dialects=dialects,
        code=code,
    )
