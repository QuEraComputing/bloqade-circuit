from typing import Sequence
from dataclasses import field, dataclass

import cirq
from kirin import ir
from kirin.emit import EmitABC, EmitFrame
from kirin.interp import MethodTable, impl
from kirin.dialects import func
from typing_extensions import Self

from .. import op, qubit, kernel


@dataclass
class EmitCirqFrame(EmitFrame):
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
    qubit_index: int = 0

    @impl(qubit.New)
    def new(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.New):
        n_qubits = frame.get(stmt.n_qubits)

        if frame.qubits is not None:
            cirq_qubits = [frame.qubits[i + self.qubit_index] for i in range(n_qubits)]
        else:
            cirq_qubits = [
                cirq.LineQubit(i + self.qubit_index) for i in range(n_qubits)
            ]

        self.qubit_index += n_qubits
        return (cirq_qubits,)

    @impl(qubit.Apply)
    def apply(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.Apply):
        op = frame.get(stmt.operator)
        qbits = frame.get(stmt.qubits)
        operation = op(*qbits)
        frame.circuit.append(operation)
        return ()
