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
    register_as_argument: bool = False,
    return_register: bool = False,
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
        register_as_argument (bool): Determine whether the resulting kernel function should accept
            a single `ilist.IList[Qubit, Any]` argument that is a list of qubits used within the
            function. This allows you to compose kernel functions generated from circuits.
            Defaults to `False`.
        return_register (bool): Determine whether the resulting kernel functionr returns a
            single value of type `ilist.IList[Qubit, Any]` that is the list of qubits used
            in the kernel function. Useful when you want to compose multiple kernel functions
            generated from circuits. Defaults to `False`.
        globals (dict[str, Any] | None): The global variables to use. Defaults to None.
        file (str | None): The file name for error reporting. Defaults to None.
        lineno_offset (int): The line number offset for error reporting. Defaults to 0.
        col_offset (int): The column number offset for error reporting. Defaults to 0.
        compactify (bool): Whether to compactify the output. Defaults to True.

    ## Usage Examples:

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

    You can also compose kernel functions generated from circuits by passing in
    and / or returning the respective quantum registers:

    ```python
    q = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(cirq.H(q[0]), cirq.CX(*q))

    get_entangled_qubits = squin.cirq.load_circuit(
        circuit, return_register=True, kernel_name="get_entangled_qubits"
    )
    get_entangled_qubits.print()

    entangle_qubits = squin.cirq.load_circuit(
        circuit, register_as_argument=True, kernel_name="entangle_qubits"
    )

    @squin.kernel
    def main():
        qreg = get_entangled_qubits()
        qreg2 = squin.qubit.new(1)
        entangle_qubits([qreg[1], qreg2[0]])
        return squin.qubit.measure(qreg2)
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
        register_as_argument=register_as_argument,
    )

    if return_register:
        return_value = target.qreg
    else:
        return_value = func.ConstantNone()
        body.blocks[0].stmts.append(return_value)

    return_node = func.Return(value_or_stmt=return_value)
    body.blocks[0].stmts.append(return_node)

    if register_as_argument:
        args = (target.qreg.type,)
    else:
        args = ()

    # NOTE: add _self as argument; need to know signature before so do it after lowering
    signature = func.Signature(args, return_node.value.type)
    body.blocks[0].args.insert_from(
        0,
        types.Generic(ir.Method, types.Tuple.where(signature.inputs), signature.output),
        kernel_name + "_self",
    )

    code = func.Function(
        sym_name=kernel_name,
        signature=signature,
        body=body,
    )

    return ir.Method(
        mod=None,
        py_func=None,
        sym_name=kernel_name,
        arg_names=[arg.name for arg in body.blocks[0].args if arg.name is not None],
        dialects=dialects,
        code=code,
    )
