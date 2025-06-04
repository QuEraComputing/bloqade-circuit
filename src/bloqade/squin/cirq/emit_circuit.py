from typing import Sequence
from dataclasses import field, dataclass

import cirq
from kirin import ir, types
from kirin.emit import EmitABC, EmitFrame
from kirin.interp import MethodTable, impl
from kirin.dialects import func
from typing_extensions import Self

from .. import op, qubit, kernel


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
        args = stmt.inputs
        ret = stmt.result

        with emit.new_frame(stmt.callee.code) as sub_frame:
            sub_frame.qubit_index = frame.qubit_index
            sub_frame.qubits = frame.qubits

            region = stmt.callee.callable_region

            # NOTE: need to set the block argument SSA values to the ones present in the frame
            # FIXME: this feels wrong, there's probably a better way to do this
            for block in region.blocks:
                # NOTE: skip self in block args, so start at index 1
                for block_arg, func_arg in zip(block.args[1:], args):
                    sub_frame.entries[block_arg] = frame.get(func_arg)

            sub_circuit = emit.run_callable_region(
                sub_frame, stmt.callee.code, region, ()
            )
            # emit.run_ssacfg_region(sub_frame, stmt.callee.callable_region, args=())

            if not ret.type.is_subseteq(types.NoneType):
                # NOTE: get the ResultValue of the return value and put it in the frame
                # FIXME: this again feels _very_ wrong, there has to be a better way
                ret_val = None
                for val in sub_frame.entries.keys():
                    for use in val.uses:
                        if isinstance(use.stmt, func.Return):
                            ret_val = val
                            break

                if ret_val is not None:
                    frame.entries[ret] = sub_frame.get(ret_val)

        frame.circuit.append(
            cirq.CircuitOperation(sub_circuit.freeze(), use_repetition_ids=False)
        )
        return ()


@op.dialect.register(key="emit.cirq")
class EmitCirqOpMethods(MethodTable):
    @impl(op.stmts.X)
    @impl(op.stmts.Y)
    @impl(op.stmts.Z)
    def pauli(
        self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.PauliOp
    ) -> tuple[cirq.Pauli]:
        cirq_pauli = getattr(cirq, stmt.name.upper())
        return (cirq_pauli,)

    @impl(op.stmts.H)
    def h(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.H):
        return (cirq.H,)

    @impl(op.stmts.Identity)
    def identity(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Identity):
        return (cirq.IdentityGate(num_qubits=stmt.sites),)

    @impl(op.stmts.Control)
    def control(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Control):
        op: cirq.Gate = frame.get(stmt.op)
        return (op.controlled(num_controls=stmt.n_controls),)


@qubit.dialect.register(key="emit.cirq")
class EmitCirqQubitMethods(MethodTable):
    @impl(qubit.New)
    def new(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.New):
        n_qubits = frame.get(stmt.n_qubits)

        if frame.qubits is not None:
            cirq_qubits = [frame.qubits[i + frame.qubit_index] for i in range(n_qubits)]
        else:
            cirq_qubits = [
                cirq.LineQubit(i + frame.qubit_index) for i in range(n_qubits)
            ]

        frame.qubit_index += n_qubits
        return (cirq_qubits,)

    @impl(qubit.Apply)
    def apply(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.Apply):
        op = frame.get(stmt.operator)
        qbits = frame.get(stmt.qubits)
        operation = op(*qbits)
        frame.circuit.append(operation)
        return ()
