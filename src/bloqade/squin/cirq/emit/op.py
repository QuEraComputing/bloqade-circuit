from typing import Sequence
from dataclasses import dataclass

import cirq
from kirin.interp import MethodTable, impl

from ... import op
from .emit_circuit import EmitCirq, EmitCirqFrame


@dataclass
class OperatorRuntimeABC:
    def num_qubits(self) -> int: ...

    def check_qubits(self, qubits: Sequence[cirq.Qid]):
        assert self.num_qubits() == len(qubits)

    def apply(self, qubits: Sequence[cirq.Qid]) -> list[cirq.Operation]:
        self.check_qubits(qubits)
        return self.unsafe_apply(qubits)

    def unsafe_apply(self, qubits: Sequence[cirq.Qid]) -> list[cirq.Operation]: ...


@dataclass
class UnsafeOperatorRuntimeABC(OperatorRuntimeABC):
    def check_qubits(self, qubits: Sequence[cirq.Qid]):
        # NOTE: let's let cirq check this one
        pass


@dataclass
class BasicOpRuntime(UnsafeOperatorRuntimeABC):
    gate: cirq.Gate

    def num_qubits(self) -> int:
        return self.gate.num_qubits()

    def unsafe_apply(self, qubits: Sequence[cirq.Qid]) -> list[cirq.Operation]:
        return [self.gate(*qubits)]


@dataclass
class ProjectorRuntime(UnsafeOperatorRuntimeABC):
    target_state: bool

    def num_qubits(self) -> int:
        return 1

    def unsafe_apply(self, qubits: Sequence[cirq.Qid]) -> list[cirq.Operation]:
        # NOTE: this doesn't scale well, but works
        sign = (-1) ** self.target_state
        p = (1 + sign * cirq.Z(*qubits)) / 2
        return [p]


@dataclass
class SpRuntime(UnsafeOperatorRuntimeABC):
    def num_qubits(self) -> int:
        return 1

    def unsafe_apply(self, qubits: Sequence[cirq.Qid]) -> list[cirq.Operation]:
        return [(cirq.X(*qubits) - 1j * cirq.Y(*qubits)) / 2]  # type: ignore  -- we're not dealing with cirq's type issues


@dataclass
class SnRuntime(UnsafeOperatorRuntimeABC):
    def num_qubits(self) -> int:
        return 1

    def unsafe_apply(self, qubits: Sequence[cirq.Qid]) -> list[cirq.Operation]:
        return [(cirq.X(*qubits) + 1j * cirq.Y(*qubits)) / 2]  # type: ignore  -- we're not dealing with cirq's type issues


@dataclass
class MultRuntime(OperatorRuntimeABC):
    lhs: OperatorRuntimeABC
    rhs: OperatorRuntimeABC

    def num_qubits(self) -> int:
        n = self.lhs.num_qubits()
        assert n == self.rhs.num_qubits()
        return n

    def unsafe_apply(self, qubits: Sequence[cirq.Qid]) -> list[cirq.Operation]:
        cirq_ops = self.rhs.unsafe_apply(qubits)
        cirq_ops.extend(self.lhs.unsafe_apply(qubits))
        return cirq_ops


@dataclass
class KronRuntime(OperatorRuntimeABC):
    lhs: OperatorRuntimeABC
    rhs: OperatorRuntimeABC

    def num_qubits(self) -> int:
        return self.lhs.num_qubits() + self.rhs.num_qubits()

    def unsafe_apply(self, qubits: Sequence[cirq.Qid]) -> list[cirq.Operation]:
        n = self.lhs.num_qubits()
        cirq_ops = self.lhs.unsafe_apply(qubits[:n])
        cirq_ops.extend(self.rhs.unsafe_apply(qubits[n:]))
        return cirq_ops


@dataclass
class ControlRuntime(OperatorRuntimeABC):
    operator: OperatorRuntimeABC
    n_controls: int

    def num_qubits(self) -> int:
        return self.n_controls + self.operator.num_qubits()

    def unsafe_apply(self, qubits: Sequence[cirq.Qid]) -> list[cirq.Operation]:
        m = len(qubits) - self.n_controls
        cirq_ops = self.operator.unsafe_apply(qubits[m:])
        controlled_ops = [cirq_op.controlled_by(*qubits[:m]) for cirq_op in cirq_ops]
        return controlled_ops


@op.dialect.register(key="emit.cirq")
class EmitCirqOpMethods(MethodTable):

    @impl(op.stmts.X)
    @impl(op.stmts.Y)
    @impl(op.stmts.Z)
    @impl(op.stmts.H)
    @impl(op.stmts.S)
    @impl(op.stmts.T)
    def basic_op(
        self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.ConstantUnitary
    ) -> tuple[BasicOpRuntime]:
        cirq_pauli = getattr(cirq, stmt.name.upper())
        return (BasicOpRuntime(cirq_pauli),)

    @impl(op.stmts.P0)
    @impl(op.stmts.P1)
    def projector(
        self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.P0 | op.stmts.P1
    ):
        return (ProjectorRuntime(isinstance(stmt, op.stmts.P1)),)

    @impl(op.stmts.Sn)
    def sn(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Sn):
        return (SnRuntime(),)

    @impl(op.stmts.Sp)
    def sp(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Sp):
        return (SpRuntime(),)

    @impl(op.stmts.Identity)
    def identity(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Identity):
        op = BasicOpRuntime(cirq.IdentityGate(num_qubits=stmt.sites))
        return (op,)

    @impl(op.stmts.Control)
    def control(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Control):
        op: OperatorRuntimeABC = frame.get(stmt.op)
        return (ControlRuntime(op, stmt.n_controls),)

    @impl(op.stmts.Kron)
    def kron(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Kron):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)
        op = KronRuntime(lhs, rhs)
        return (op,)

    @impl(op.stmts.Mult)
    def mult(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Mult):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)
        op = MultRuntime(lhs, rhs)
        return (op,)

    @impl(op.stmts.Adjoint)
    def adjoint(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Adjoint):
        raise NotImplementedError("TODO")

    @impl(op.stmts.Scale)
    def scale(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Scale):
        raise NotImplementedError("TODO")

    @impl(op.stmts.U3)
    def u3(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.U3):
        raise NotImplementedError("TODO")

    @impl(op.stmts.PhaseOp)
    def phaseop(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.PhaseOp):
        raise NotImplementedError("TODO")

    @impl(op.stmts.ShiftOp)
    def shiftop(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.ShiftOp):
        raise NotImplementedError("TODO")

    @impl(op.stmts.Reset)
    def reset(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Reset):
        raise NotImplementedError("TODO")

    @impl(op.stmts.PauliString)
    def pauli_string(
        self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.PauliString
    ):
        raise NotImplementedError("TODO")
