from typing import Any

import cirq
from kirin import ir, types
from kirin.passes import inline
from kirin.dialects import func

from . import lowering as lowering
from .. import op, kernel
from .lowering import Squin
from .emit_circuit import EmitCirq


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
    """Converts a cirq.Circuit object into a squin kernel.

    Args:
        circuit (cirq.Circuit): The circuit to load.

    Keyword Args:
        kernel_name (str): The name of the kernel to load. Defaults to "main".
        dialects (ir.DialectGroup | None): The dialects to use. Defaults to `squin.kernel`.
        globals (dict[str, Any] | None): The global variables to use. Defaults to None.
        file (str | None): The file name for error reporting. Defaults to None.
        lineno_offset (int): The line number offset for error reporting. Defaults to 0.
        col_offset (int): The column number offset for error reporting. Defaults to 0.
        compactify (bool): Whether to compactify the output. Defaults to True.

    Example:

    ```python
    # from cirq's "hello qubit" example
    import cirq
    from bloqade import squin

    # Pick a qubit.
    qubit = cirq.GridQubit(0, 0)

    # Create a circuit.
    circuit = cirq.Circuit(
        cirq.X(qubit)**0.5,  # Square root of NOT.
        cirq.measure(qubit, key='m')  # Measurement.
    )

    # load the circuit as squin
    main = squin.load_circuit(circuit)

    # print the resulting IR
    main.print()
    ```
    """

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


def emit_circuit(
    mt: ir.Method,
    args=(),
    qubits: list[cirq.Qid] | None = None,
    qubit_type=cirq.LineQubit,
) -> cirq.Circuit:
    emitter = EmitCirq()

    mt_ = mt.similar(mt.dialects)

    # NOTE: inline squin shorthand wrappers (e.g. cx)
    def should_inline(x: func.Function) -> bool:
        try:
            getattr(op, x.sym_name)
            return True
        except AttributeError:
            # awww yeah, idiomatic python
            return False

    inline_pass = inline.InlinePass(mt_.dialects, herustic=should_inline)
    inline_pass(mt_)

    return emitter.run(mt_, args=args)


def dump_circuit(mt: ir.Method, args=(), **kwargs):
    circuit = emit_circuit(mt, args=args)
    return cirq.to_json(circuit, **kwargs)
