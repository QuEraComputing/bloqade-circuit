from typing import Any, Sequence

import cirq
from kirin import ir, types
from kirin.emit import EmitError
from kirin.dialects import func

from . import lowering as lowering
from .. import kernel

# NOTE: just to register methods
from .emit import op as op, noise as noise, qubit as qubit
from .lowering import Squin
from ..noise.rewrite import RewriteNoiseStmts
from .emit.emit_circuit import EmitCirq


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
    qubits: Sequence[cirq.Qid] | None = None,
) -> cirq.Circuit:
    """Converts a squin.kernel method to a cirq.Circuit object.

    Args:
        mt (ir.Method): The kernel method from which to construct the circuit.

    Keyword Args:
        qubits (Sequence[cirq.Qid] | None):
            A list of qubits to use as the qubits in the circuit. Defaults to None.
            If this is None, then `cirq.LineQubit`s are inserted for every `squin.qubit.new`
            statement in the order they appear inside the kernel.
            **Note**: If a list of qubits is provided, make sure that there is a sufficient
            number of qubits for the resulting circuit.

    ## Examples:

    Here's a very basic example:

    ```python
    from bloqade import squin

    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        h = squin.op.h()
        squin.qubit.apply(h, q[0])
        cx = squin.op.cx()
        squin.qubit.apply(cx, q)

    circuit = squin.cirq.emit_circuit(main)

    print(circuit)
    ```

    You can also compose multiple kernels. Those are emitted as subcircuits within the "main" circuit.
    Subkernels can accept arguments and return a value.

    ```python
    from bloqade import squin
    from kirin.dialects import ilist
    from typing import Literal
    import cirq

    @squin.kernel
    def entangle(q: ilist.IList[squin.qubit.Qubit, Literal[2]]):
        h = squin.op.h()
        squin.qubit.apply(h, q[0])
        cx = squin.op.cx()
        squin.qubit.apply(cx, q)
        return cx

    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        cx = entangle(q)
        q2 = squin.qubit.new(3)
        squin.qubit.apply(cx, [q[1], q2[2]])


    # custom list of qubits on grid
    qubits = [cirq.GridQubit(i, i+1) for i in range(5)]

    circuit = squin.cirq.emit_circuit(main, qubits=qubits)
    print(circuit)

    ```

    We also passed in a custom list of qubits above. This allows you to provide a custom geometry
    and manipulate the qubits in other circuits directly written in cirq as well.
    """

    if isinstance(mt.code, func.Function) and not mt.code.signature.output.is_subseteq(
        types.NoneType
    ):
        raise EmitError(
            "The method you are trying to convert to a circuit has a return value, but returning from a circuit is not supported."
        )

    emitter = EmitCirq(qubits=qubits)

    # Rewrite noise statements
    mt_ = mt.similar(mt.dialects)
    RewriteNoiseStmts(mt_.dialects)(mt_)

    return emitter.run(mt_, args=())


def dump_circuit(mt: ir.Method, qubits: Sequence[cirq.Qid] | None = None, **kwargs):
    """Converts a squin.kernel method to a cirq.Circuit object and dumps it as JSON.

    This just runs `emit_circuit` and calls the `cirq.to_json` function to emit a JSON.

    Args:
        mt (ir.Method): The kernel method from which to construct the circuit.

    Keyword Args:
        qubits (Sequence[cirq.Qid] | None):
            A list of qubits to use as the qubits in the circuit. Defaults to None.
            If this is None, then `cirq.LineQubit`s are inserted for every `squin.qubit.new`
            statement in the order they appear inside the kernel.
            **Note**: If a list of qubits is provided, make sure that there is a sufficient
            number of qubits for the resulting circuit.

    """
    circuit = emit_circuit(mt, qubits=qubits)
    return cirq.to_json(circuit, **kwargs)
