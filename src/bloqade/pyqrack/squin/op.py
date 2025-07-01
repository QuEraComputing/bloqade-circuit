from kirin import interp

from bloqade.squin import op
from bloqade.pyqrack.base import PyQrackInterpreter

from .runtime import (
    SnRuntime,
    SpRuntime,
    U3Runtime,
    RotRuntime,
    KronRuntime,
    MultRuntime,
    ResetRuntime,
    ScaleRuntime,
    AdjointRuntime,
    ControlRuntime,
    PhaseOpRuntime,
    IdentityRuntime,
    OperatorRuntime,
    ProjectorRuntime,
    OperatorRuntimeABC,
    PauliStringRuntime,
)


@op.dialect.register(key="pyqrack")
class PyQrackMethods(interp.MethodTable):

    @interp.impl(op.stmts.Kron)
    def kron(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.Kron
    ) -> tuple[OperatorRuntimeABC]:
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)
        return (KronRuntime(lhs, rhs),)

    @interp.impl(op.stmts.Mult)
    def mult(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.Mult
    ) -> tuple[OperatorRuntimeABC]:
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)
        return (MultRuntime(lhs, rhs),)

    @interp.impl(op.stmts.Adjoint)
    def adjoint(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.Adjoint
    ) -> tuple[OperatorRuntimeABC]:
        op = frame.get(stmt.op)
        return (AdjointRuntime(op),)

    @interp.impl(op.stmts.Scale)
    def scale(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.Scale
    ) -> tuple[OperatorRuntimeABC]:
        op = frame.get(stmt.op)
        factor = frame.get(stmt.factor)
        return (ScaleRuntime(op, factor),)

    @interp.impl(op.stmts.Control)
    def control(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.Control
    ) -> tuple[OperatorRuntimeABC]:
        op = frame.get(stmt.op)
        n_controls = stmt.n_controls
        rt = ControlRuntime(
            op=op,
            n_controls=n_controls,
        )
        return (rt,)

    @interp.impl(op.stmts.Rot)
    def rot(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.Rot
    ) -> tuple[OperatorRuntimeABC]:
        axis = frame.get(stmt.axis)
        angle = frame.get(stmt.angle)
        return (RotRuntime(axis, angle),)

    @interp.impl(op.stmts.Identity)
    def identity(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.Identity
    ) -> tuple[OperatorRuntimeABC]:
        return (IdentityRuntime(sites=stmt.sites),)

    @interp.impl(op.stmts.PhaseOp)
    @interp.impl(op.stmts.ShiftOp)
    def phaseop(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: op.stmts.PhaseOp | op.stmts.ShiftOp,
    ) -> tuple[OperatorRuntimeABC]:
        theta = frame.get(stmt.theta)
        global_ = isinstance(stmt, op.stmts.PhaseOp)
        return (PhaseOpRuntime(theta, global_=global_),)

    @interp.impl(op.stmts.Reset)
    @interp.impl(op.stmts.ResetToOne)
    def reset(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: op.stmts.Reset | op.stmts.ResetToOne,
    ) -> tuple[OperatorRuntimeABC]:
        target_state = isinstance(stmt, op.stmts.ResetToOne)
        return (ResetRuntime(target_state=target_state),)

    @interp.impl(op.stmts.X)
    @interp.impl(op.stmts.Y)
    @interp.impl(op.stmts.Z)
    @interp.impl(op.stmts.H)
    @interp.impl(op.stmts.S)
    @interp.impl(op.stmts.T)
    def operator(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: (
            op.stmts.X | op.stmts.Y | op.stmts.Z | op.stmts.H | op.stmts.S | op.stmts.T
        ),
    ) -> tuple[OperatorRuntimeABC]:
        return (OperatorRuntime(method_name=stmt.name.lower()),)

    @interp.impl(op.stmts.P0)
    @interp.impl(op.stmts.P1)
    def projector(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: op.stmts.P0 | op.stmts.P1,
    ) -> tuple[OperatorRuntimeABC]:
        state = isinstance(stmt, op.stmts.P1)
        return (ProjectorRuntime(to_state=state),)

    @interp.impl(op.stmts.Sp)
    def sp(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.Sp
    ) -> tuple[OperatorRuntimeABC]:
        return (SpRuntime(),)

    @interp.impl(op.stmts.Sn)
    def sn(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.Sn
    ) -> tuple[OperatorRuntimeABC]:
        return (SnRuntime(),)

    @interp.impl(op.stmts.U3)
    def u3(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.U3
    ) -> tuple[OperatorRuntimeABC]:
        theta = frame.get(stmt.theta)
        phi = frame.get(stmt.phi)
        lam = frame.get(stmt.lam)
        return (U3Runtime(theta, phi, lam),)

    @interp.impl(op.stmts.PauliString)
    def clifford_string(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: op.stmts.PauliString,
    ) -> tuple[OperatorRuntimeABC]:
        string = stmt.string
        ops = [OperatorRuntime(method_name=name.lower()) for name in stmt.string]
        return (PauliStringRuntime(string, ops),)
