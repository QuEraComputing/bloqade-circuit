import cirq
from kirin.interp import MethodTable, impl

from ... import op
from .emit_circuit import EmitCirq, EmitCirqFrame


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

    @impl(op.stmts.S)
    def s(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.S):
        return (cirq.S,)

    @impl(op.stmts.T)
    def t(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.T):
        return (cirq.T,)

    @impl(op.stmts.P0)
    def p0(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.P0):
        raise NotImplementedError("TODO")

    @impl(op.stmts.P1)
    def p1(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.P1):
        raise NotImplementedError("TODO")

    @impl(op.stmts.Sn)
    def sn(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Sn):
        raise NotImplementedError("TODO")

    @impl(op.stmts.Sp)
    def sp(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Sp):
        raise NotImplementedError("TODO")

    @impl(op.stmts.Identity)
    def identity(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Identity):
        return (cirq.IdentityGate(num_qubits=stmt.sites),)

    @impl(op.stmts.Control)
    def control(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Control):
        op: cirq.Gate = frame.get(stmt.op)
        return (op.controlled(num_controls=stmt.n_controls),)

    @impl(op.stmts.Kron)
    def kron(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Kron):
        # lhs = frame.get(stmt.lhs)
        # rhs = frame.get(stmt.rhs)
        raise NotImplementedError("TODO")

    @impl(op.stmts.Mult)
    def mult(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: op.stmts.Mult):
        # lhs = frame.get(stmt.lhs)
        # rhs = frame.get(stmt.rhs)
        raise NotImplementedError("TODO")

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
