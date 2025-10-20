from typing import Sequence
from warnings import warn
from dataclasses import field, dataclass

import cirq
from kirin import ir, types, interp
from kirin.emit import EmitABC, EmitFrame
from kirin.interp import MethodTable, impl, InterpreterError
from kirin.dialects import func
from typing_extensions import Self

from bloqade.squin import kernel


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
            If this is None, then `cirq.LineQubit`s are inserted for every `squin.qubit.new`
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

    circuit = squin.cirq.emit_circuit(main, circuit_qubits=qubits)
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
        raise InterpreterError(
            "The method you are trying to convert to a circuit has a return value, but returning from a circuit is not supported."
            " Set `ignore_returns = True` in order to simply ignore the return values and emit a circuit."
        )

    if len(args) != len(mt.args):
        raise ValueError(
            f"The method from which you're trying to emit a circuit takes {len(mt.args)} as input, but you passed in {len(args)} via the `args` keyword!"
        )

    emitter = EmitCirq(qubits=qubits)

    return emitter.run(mt, args=args)


@dataclass
class EmitCirqFrame(EmitFrame):
    qubit_index: int = 0
    qubits: Sequence[cirq.Qid] | None = None
    circuit: cirq.Circuit = field(default_factory=cirq.Circuit)


def _default_kernel():
    return kernel


@dataclass
class EmitCirq(EmitABC[EmitCirqFrame, cirq.Circuit]):
    keys = ("emit.cirq", "emit.main")
    dialects: ir.DialectGroup = field(default_factory=_default_kernel)
    void = cirq.Circuit()
    qubits: Sequence[cirq.Qid] | None = None
    _cached_circuit_operations: dict[int, cirq.CircuitOperation] = field(
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

        results = self.frame_eval(frame, code)
        if isinstance(results, tuple):
            if len(results) == 0:
                return self.void
            elif len(results) == 1:
                return results[0]
        raise interp.InterpreterError(f"Unexpected results {results}")

    def emit_block(self, frame: EmitCirqFrame, block: ir.Block) -> cirq.Circuit:
        for stmt in block.stmts:
            result = self.frame_eval(frame, stmt)
            if isinstance(result, tuple):
                frame.set_values(stmt.results, result)

        return frame.circuit


@func.dialect.register(key="emit.cirq")
class FuncEmit(MethodTable):

    @impl(func.Function)
    def emit_func(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: func.Function):
        emit.run_ssacfg_region(frame, stmt.body, ())
        return (frame.circuit,)

    @impl(func.Invoke)
    def emit_invoke(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: func.Invoke):
        stmt_hash = hash((stmt.callee, stmt.inputs))
        if (
            cached_circuit_op := emit._cached_circuit_operations.get(stmt_hash)
        ) is not None:
            # NOTE: cache hit
            frame.circuit.append(cached_circuit_op)
            return ()

        ret = stmt.result

        with emit.new_frame(stmt.callee.code, has_parent_access=True) as sub_frame:
            sub_frame.qubit_index = frame.qubit_index
            sub_frame.qubits = frame.qubits

            region = stmt.callee.callable_region
            if len(region.blocks) > 1:
                raise InterpreterError(
                    "Subroutine with more than a single block encountered. This is not supported!"
                )

            # NOTE: get the arguments, "self" is just an empty circuit
            method_self = emit.void
            args = [frame.get(arg_) for arg_ in stmt.inputs]
            emit.run_ssacfg_region(
                sub_frame, stmt.callee.callable_region, args=(method_self, *args)
            )
            sub_circuit = sub_frame.circuit

            # NOTE: check to see if the call terminates with a return value and fetch the value;
            # we don't support multiple return statements via control flow so we just pick the first one
            block = region.blocks[0]
            return_stmt = next(
                (stmt for stmt in block.stmts if isinstance(stmt, func.Return)), None
            )
            if return_stmt is not None:
                frame.entries[ret] = sub_frame.get(return_stmt.value)

        circuit_op = cirq.CircuitOperation(
            sub_circuit.freeze(), use_repetition_ids=False
        )
        emit._cached_circuit_operations[stmt_hash] = circuit_op
        frame.circuit.append(circuit_op)
        return ()
