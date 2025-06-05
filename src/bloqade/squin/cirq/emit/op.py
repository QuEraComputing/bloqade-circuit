import math
from typing import Sequence
from numbers import Number
from dataclasses import dataclass

import cirq
import numpy as np
from kirin.interp import MethodTable, impl

from ... import op
from .emit_circuit import EmitCirq, EmitCirqFrame


@dataclass
class OperatorRuntimeABC:
    def num_qubits(self) -> int: ...

    def check_qubits(self, qubits: Sequence[cirq.Qid]):
        assert self.num_qubits() == len(qubits)

    def apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        self.check_qubits(qubits)
        return self.unsafe_apply(qubits, adjoint=adjoint)

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]: ...


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


@dataclass
class UnitaryRuntime(BasicOpRuntime):
    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        exponent = (-1) ** adjoint
        return [self.gate(*qubits) ** exponent]


@dataclass
class HermitianRuntime(BasicOpRuntime):
    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        return [self.gate(*qubits)]


@dataclass
class ProjectorRuntime(UnsafeOperatorRuntimeABC):
    target_state: bool

    def num_qubits(self) -> int:
        return 1

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        # NOTE: this doesn't scale well, but works
        sign = (-1) ** self.target_state
        p = (1 + sign * cirq.Z(*qubits)) / 2
        return [p]


@dataclass
class SpRuntime(UnsafeOperatorRuntimeABC):
    def num_qubits(self) -> int:
        return 1

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        if adjoint:
            return SnRuntime().unsafe_apply(qubits, adjoint=False)

        return [(cirq.X(*qubits) - 1j * cirq.Y(*qubits)) / 2]  # type: ignore  -- we're not dealing with cirq's type issues


@dataclass
class SnRuntime(UnsafeOperatorRuntimeABC):
    def num_qubits(self) -> int:
        return 1

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        if adjoint:
            return SpRuntime().unsafe_apply(qubits, adjoint=False)

        return [(cirq.X(*qubits) + 1j * cirq.Y(*qubits)) / 2]  # type: ignore  -- we're not dealing with cirq's type issues


@dataclass
class MultRuntime(OperatorRuntimeABC):
    lhs: OperatorRuntimeABC
    rhs: OperatorRuntimeABC

    def num_qubits(self) -> int:
        n = self.lhs.num_qubits()
        assert n == self.rhs.num_qubits()
        return n

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        rhs = self.rhs.unsafe_apply(qubits, adjoint=adjoint)
        lhs = self.lhs.unsafe_apply(qubits, adjoint=adjoint)

        if adjoint:
            return lhs + rhs
        else:
            return rhs + lhs


@dataclass
class KronRuntime(OperatorRuntimeABC):
    lhs: OperatorRuntimeABC
    rhs: OperatorRuntimeABC

    def num_qubits(self) -> int:
        return self.lhs.num_qubits() + self.rhs.num_qubits()

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        n = self.lhs.num_qubits()
        cirq_ops = self.lhs.unsafe_apply(qubits[:n], adjoint=adjoint)
        cirq_ops.extend(self.rhs.unsafe_apply(qubits[n:], adjoint=adjoint))
        return cirq_ops


@dataclass
class ControlRuntime(OperatorRuntimeABC):
    operator: OperatorRuntimeABC
    n_controls: int

    def num_qubits(self) -> int:
        return self.n_controls + self.operator.num_qubits()

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        m = len(qubits) - self.n_controls
        cirq_ops = self.operator.unsafe_apply(qubits[m:], adjoint=adjoint)
        controlled_ops = [cirq_op.controlled_by(*qubits[:m]) for cirq_op in cirq_ops]
        return controlled_ops


@dataclass
class AdjointRuntime(OperatorRuntimeABC):
    operator: OperatorRuntimeABC

    def num_qubits(self) -> int:
        return self.operator.num_qubits()

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        # NOTE: to account for e.g. adjoint(adjoint(op))
        passed_on_adjoint = not adjoint
        return self.operator.unsafe_apply(qubits, adjoint=passed_on_adjoint)


@dataclass
class U3Runtime(UnsafeOperatorRuntimeABC):
    theta: float
    phi: float
    lam: float

    def num_qubits(self) -> int:
        return 1

    def angles(self, adjoint: bool) -> tuple[float, float, float]:
        if adjoint:
            # NOTE: adjoint(U(theta, phi, lam)) == U(-theta, -lam, -phi)
            return -self.theta, -self.lam, -self.phi
        else:
            return self.theta, self.phi, self.lam

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        theta, phi, lam = self.angles(adjoint=adjoint)

        ops = [
            cirq.Rz(rads=lam)(*qubits),
            cirq.Rx(rads=math.pi / 2)(*qubits),
            cirq.Rz(rads=theta)(*qubits),
            cirq.Rx(rads=-math.pi / 2)(*qubits),
            cirq.Rz(rads=phi)(*qubits),
        ]

        return ops


@dataclass
class ScaleRuntime(OperatorRuntimeABC):
    factor: Number
    operator: OperatorRuntimeABC

    def num_qubits(self) -> int:
        return self.operator.num_qubits()

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        cirq_ops = self.operator.unsafe_apply(qubits=qubits, adjoint=adjoint)
        return [self.factor * cirq_ops[0]] + cirq_ops[1:]  # type: ignore


@dataclass
class PauliStringRuntime(OperatorRuntimeABC):
    string: str

    def num_qubits(self) -> int:
        return len(self.string)

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        pauli_mapping = {
            qbit: pauli_label for (qbit, pauli_label) in zip(qubits, self.string)
        }
        return [cirq.PauliString(pauli_mapping)]


@op.dialect.register(key="emit.cirq")
class EmitCirqOpMethods(MethodTable):

    @impl(op.stmts.X)
    @impl(op.stmts.Y)
    @impl(op.stmts.Z)
    @impl(op.stmts.H)
    def hermitian(
        self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.ConstantUnitary
    ):
        cirq_op = getattr(cirq, stmt.name.upper())
        return (HermitianRuntime(cirq_op),)

    @impl(op.stmts.S)
    @impl(op.stmts.T)
    def unitary(
        self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.ConstantUnitary
    ):
        cirq_op = getattr(cirq, stmt.name.upper())
        return (UnitaryRuntime(cirq_op),)

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
        op = HermitianRuntime(cirq.IdentityGate(num_qubits=stmt.sites))
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
        op_ = frame.get(stmt.op)
        return (AdjointRuntime(op_),)

    @impl(op.stmts.Scale)
    def scale(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Scale):
        op_ = frame.get(stmt.op)
        factor = frame.get(stmt.factor)
        return (ScaleRuntime(operator=op_, factor=factor),)

    @impl(op.stmts.U3)
    def u3(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.U3):
        theta = frame.get(stmt.theta)
        phi = frame.get(stmt.phi)
        lam = frame.get(stmt.lam)
        return (U3Runtime(theta=theta, phi=phi, lam=lam),)

    @impl(op.stmts.PhaseOp)
    def phaseop(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.PhaseOp):
        theta = frame.get(stmt.theta)
        op_ = HermitianRuntime(cirq.IdentityGate(num_qubits=1))
        return (ScaleRuntime(operator=op_, factor=np.exp(1j * theta)),)

    @impl(op.stmts.ShiftOp)
    def shiftop(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.ShiftOp):
        theta = frame.get(stmt.theta)

        # NOTE: ShiftOp(theta) == U3(pi, theta, 0)
        return (U3Runtime(math.pi, theta, 0),)

    @impl(op.stmts.Reset)
    def reset(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Reset):
        return (HermitianRuntime(cirq.ResetChannel()),)

    @impl(op.stmts.PauliString)
    def pauli_string(
        self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.PauliString
    ):
        return (PauliStringRuntime(stmt.string),)
