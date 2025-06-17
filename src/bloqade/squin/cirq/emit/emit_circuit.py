from typing import Sequence
from dataclasses import field, dataclass

import cirq
from kirin import ir
from kirin.emit import EmitABC, EmitError, EmitFrame
from kirin.interp import MethodTable, impl
from kirin.dialects import func
from typing_extensions import Self

from ... import kernel


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

    def emit_block(self, frame: EmitCirqFrame, block: ir.Block) -> cirq.Circuit:
        for stmt in block.stmts:
            result = self.eval_stmt(frame, stmt)
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
                raise EmitError(
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
