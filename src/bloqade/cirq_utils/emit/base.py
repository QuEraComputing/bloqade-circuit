from typing import Sequence
from warnings import warn
from dataclasses import field, dataclass

import cirq
from kirin import ir, types, interp
from kirin.emit import EmitABC, EmitError, EmitFrame
from kirin.interp import MethodTable, impl
from kirin.dialects import py, func
from typing_extensions import Self

from bloqade.squin import kernel
from bloqade.rewrite.passes import AggressiveUnroll


def emit_circuit(
    mt: ir.Method,
    qubits: Sequence[cirq.Qid] | None = None,
    circuit_qubits: Sequence[cirq.Qid] | None = None,
    args: tuple = (),
    ignore_returns: bool = False,
) -> cirq.Circuit:
    """Converts a squin.kernel method to a cirq.Circuit object.

    Args:
        mt (ir.Method): The kernel method from which to construct the circuit.

    Keyword Args:
        circuit_qubits (Sequence[cirq.Qid] | None):
            A list of qubits to use as the qubits in the circuit. Defaults to None.
            If this is None, then `cirq.LineQubit`s are inserted for every `squin.qalloc`
            statement in the order they appear inside the kernel.
            **Note**: If a list of qubits is provided, make sure that there is a sufficient
            number of qubits for the resulting circuit.
        args (tuple):
            The arguments of the kernel function from which to emit a circuit.
        ignore_returns (bool):
            If `False`, emitting a circuit from a kernel that returns a value will error.
            Set it to `True` in order to ignore the return value(s). Defaults to `False`.

    ## Examples:

    Here's a very basic example:

    ```python
    from bloqade import squin
    from bloqade.cirq_utils import emit_circuit

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])

    circuit = emit_circuit(main)

    print(circuit)
    ```

    You can also compose multiple kernels. Those are emitted as subcircuits within the "main" circuit.
    Subkernels can accept arguments and return a value.

    ```python
    from bloqade import squin
    from bloqade.cirq_utils import emit_circuit
    from kirin.dialects import ilist
    from typing import Literal
    import cirq

    @squin.kernel
    def entangle(q: ilist.IList[squin.qubit.Qubit, Literal[2]]):
        squin.h(q[0])
        squin.cx(q[0], q[1])

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        q2 = squin.qalloc(3)
        squin.cx(q[1], q2[2])


    # custom list of qubits on grid
    qubits = [cirq.GridQubit(i, i+1) for i in range(5)]

    circuit = emit_circuit(main, circuit_qubits=qubits)
    print(circuit)

    ```

    We also passed in a custom list of qubits above. This allows you to provide a custom geometry
    and manipulate the qubits in other circuits directly written in cirq as well.
    """

    if circuit_qubits is None and qubits is not None:
        circuit_qubits = qubits
        warn(
            "The keyword argument `qubits` is deprecated. Use `circuit_qubits` instead."
        )

    if (
        not ignore_returns
        and isinstance(mt.code, func.Function)
        and not mt.code.signature.output.is_subseteq(types.NoneType)
    ):
        raise EmitError(
            "The method you are trying to convert to a circuit has a return value, but returning from a circuit is not supported."
            " Set `ignore_returns = True` in order to simply ignore the return values and emit a circuit."
        )

    if len(args) != len(mt.args):
        raise ValueError(
            f"The method from which you're trying to emit a circuit takes {len(mt.args)} as input, but you passed in {len(args)} via the `args` keyword!"
        )

    emitter = EmitCirq(qubits=circuit_qubits)

    symbol_op_trait = mt.code.get_trait(ir.SymbolOpInterface)
    if (symbol_op_trait := mt.code.get_trait(ir.SymbolOpInterface)) is None:
        raise EmitError("The method is not a symbol, cannot emit circuit!")

    sym_name = symbol_op_trait.get_sym_name(mt.code).unwrap()

    if (signature_trait := mt.code.get_trait(ir.HasSignature)) is None:
        raise EmitError(
            f"The method {sym_name} does not have a signature, cannot emit circuit!"
        )

    signature = signature_trait.get_signature(mt.code)
    new_signature = func.Signature(inputs=(), output=signature.output)

    callable_region = mt.callable_region.clone()
    entry_block = callable_region.blocks[0]
    args_ssa = list(entry_block.args)
    first_stmt = entry_block.first_stmt

    assert first_stmt is not None, "Method has no statements!"
    if len(args_ssa) - 1 != len(args):
        raise EmitError(
            f"The method {sym_name} takes {len(args_ssa) - 1} arguments, but you passed in {len(args)} via the `args` keyword!"
        )

    for arg, arg_ssa in zip(args, args_ssa[1:], strict=True):
        (value := py.Constant(arg)).insert_before(first_stmt)
        arg_ssa.replace_by(value.result)
        entry_block.args.delete(arg_ssa)

    new_func = func.Function(
        sym_name=sym_name, body=callable_region, signature=new_signature
    )
    mt_ = ir.Method(None, None, sym_name, [], mt.dialects, new_func)

    AggressiveUnroll(mt_.dialects).fixpoint(mt_)
    return emitter.run(mt_, args=())


@dataclass
class EmitCirqFrame(EmitFrame):
    qubit_index: int = 0
    qubits: Sequence[cirq.Qid] | None = None
    circuit: cirq.Circuit = field(default_factory=cirq.Circuit)


def _default_kernel():
    return kernel


@dataclass
class EmitCirq(EmitABC[EmitCirqFrame, cirq.Circuit]):
    keys = ["emit.cirq", "main"]
    dialects: ir.DialectGroup = field(default_factory=_default_kernel)
    void = cirq.Circuit()
    qubits: Sequence[cirq.Qid] | None = None
    _cached_invokes: dict[int, cirq.FrozenCircuit] = field(
        init=False, default_factory=dict
    )

    def initialize(self) -> Self:
        return super().initialize()

    def initialize_frame(
        self, code: ir.Statement, *, has_parent_access: bool = False
    ) -> EmitCirqFrame:
        return EmitCirqFrame(
            code, has_parent_access=has_parent_access, qubits=self.qubits
        )

    def run_method(self, method: ir.Method, args: tuple[cirq.Circuit, ...]):
        return self.run_callable(method.code, args)

    def run_callable_region(
        self,
        frame: EmitCirqFrame,
        code: ir.Statement,
        region: ir.Region,
        args: tuple,
    ):
        if len(region.blocks) > 0:
            block_args = list(region.blocks[0].args)
            # NOTE: skip self arg
            frame.set_values(block_args[1:], args)

        results = self.eval_stmt(frame, code)
        if isinstance(results, tuple):
            if len(results) == 0:
                return self.void
            elif len(results) == 1:
                return results[0]
        raise interp.InterpreterError(f"Unexpected results {results}")

    def emit_block(self, frame: EmitCirqFrame, block: ir.Block) -> cirq.Circuit:
        for stmt in block.stmts:
            result = self.eval_stmt(frame, stmt)
            if isinstance(result, tuple):
                frame.set_values(stmt.results, result)

        return frame.circuit


@func.dialect.register(key="emit.cirq")
class __FuncEmit(MethodTable):

    @impl(func.Function)
    def emit_func(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: func.Function):
        emit.run_ssacfg_region(frame, stmt.body, ())
        return (frame.circuit,)

    @impl(func.Invoke)
    def emit_invoke(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: func.Invoke):
        raise EmitError(
            "Function invokes should need to be inlined! "
            "If you called the emit_circuit method, that should have happened, please report this issue."
        )

    @impl(func.Return)
    def return_(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: func.Return):
        # NOTE: should only be hit if ignore_returns == True
        return ()


@py.indexing.dialect.register(key="emit.cirq")
class __Concrete(interp.MethodTable):

    @interp.impl(py.indexing.GetItem)
    def getindex(self, interp, frame: interp.Frame, stmt: py.indexing.GetItem):
        # NOTE: no support for indexing into single statements in cirq
        return ()
