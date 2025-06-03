from dataclasses import field, dataclass

import cirq
from kirin import ir
from kirin.emit import EmitABC, EmitFrame
from kirin.interp import MethodTable, impl
from kirin.dialects import func
from typing_extensions import Self

from .. import op, qubit, kernel

# TODO: move to separate types.py file to share with lowering
CirqNode = cirq.Circuit | cirq.Moment | cirq.Gate | cirq.Qid | cirq.Operation

DecomposeNode = (
    cirq.SwapPowGate
    | cirq.ISwapPowGate
    | cirq.PhasedXPowGate
    | cirq.PhasedXZGate
    | cirq.CSwapGate
)

CirqType = CirqNode  # typing.TypeVar("CirqType", bound=CirqNode)


@dataclass
class EmitCirqFrame(EmitFrame):
    qubit_type: type[cirq.Qid] = cirq.LineQubit
    qubits: list[cirq.Qid] = field(default_factory=list)
    circuit: cirq.Circuit = field(default_factory=cirq.Circuit)


def _default_kernel():
    return kernel


@dataclass
class EmitCirq(EmitABC[EmitCirqFrame, CirqType | None]):
    keys = ["emit.cirq", "main"]
    dialects: ir.DialectGroup = field(default_factory=_default_kernel)
    void = None
    qubits: list[cirq.Qid] = field(default_factory=list)

    def initialize(self) -> Self:
        return super().initialize()

    def initialize_frame(
        self, code: ir.Statement, *, has_parent_access: bool = False
    ) -> EmitCirqFrame:
        return EmitCirqFrame(code, has_parent_access=has_parent_access)

    def run_method(self, method: ir.Method, args: tuple[CirqType | None, ...]):
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
    def x(
        self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.X
    ) -> tuple[cirq.Pauli]:
        return (cirq.X,)


@qubit.dialect.register(key="emit.cirq")
class EmitCirqQubitMethods(MethodTable):
    qubit_index: int = 0

    @impl(qubit.New)
    def new(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.New):
        n_qubits = frame.get(stmt.n_qubits)

        # TODO: store in frame separately; use address analysis
        cirq_qubits = [cirq.LineQubit(i + self.qubit_index) for i in range(n_qubits)]
        self.qubit_index += n_qubits
        return (cirq_qubits,)

    @impl(qubit.Apply)
    def apply(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.Apply):
        op = frame.get(stmt.operator)
        qbits = frame.get(stmt.qubits)
        operation = op(*qbits)
        frame.circuit.append(operation)
        return ()
