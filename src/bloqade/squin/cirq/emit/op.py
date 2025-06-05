import math

import cirq
import numpy as np
from kirin.interp import MethodTable, impl

from ... import op
from .runtime import (
    SnRuntime,
    SpRuntime,
    U3Runtime,
    KronRuntime,
    MultRuntime,
    ScaleRuntime,
    AdjointRuntime,
    ControlRuntime,
    UnitaryRuntime,
    HermitianRuntime,
    ProjectorRuntime,
    OperatorRuntimeABC,
    PauliStringRuntime,
)
from .emit_circuit import EmitCirq, EmitCirqFrame


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
