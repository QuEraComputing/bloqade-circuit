from kirin import interp

from bloqade.squin import op
from bloqade.pyqrack.base import PyQrackInterpreter

from .runtime import (
    KronRuntime,
    MultRuntime,
    ScaleRuntime,
    AdjointRuntime,
    ControlRuntime,
    IdentityRuntime,
    OperatorRuntime,
    ProjectorRuntime,
)


@op.dialect.register(key="pyqrack")
class PyQrackMethods(interp.MethodTable):

    @interp.impl(op.stmts.Kron)
    def kron(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.Kron
    ):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)
        return (KronRuntime(lhs, rhs),)

    @interp.impl(op.stmts.Mult)
    def mult(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.Mult
    ):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)
        return (MultRuntime(lhs, rhs),)

    @interp.impl(op.stmts.Adjoint)
    def adjoint(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.Adjoint
    ):
        op = frame.get(stmt.op)
        return (AdjointRuntime(op),)

    @interp.impl(op.stmts.Scale)
    def scale(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.Scale
    ):
        op = frame.get(stmt.op)
        factor = frame.get(stmt.factor)
        return (ScaleRuntime(op, factor),)

    @interp.impl(op.stmts.Control)
    def control(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.Control
    ):
        op = frame.get(stmt.op)
        n_controls = stmt.n_controls
        rt = ControlRuntime(
            op=op,
            n_controls=n_controls,
        )
        return (rt,)

    # @interp.impl(op.stmts.Rot)
    # def rot(self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.Rot):
    #     axis: ir.SSAValue = info.argument(OpType)
    #     angle: ir.SSAValue = info.argument(types.Float)
    #     result: ir.ResultValue = info.result(OpType)

    @interp.impl(op.stmts.Identity)
    def identity(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.Identity
    ):
        return (IdentityRuntime(sites=stmt.sites),)

    # @interp.impl(op.stmts.PhaseOp)
    # def phaseop(
    #     self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.PhaseOp
    # ):
    #     """
    #     A phase operator.

    #     $$
    #     PhaseOp(theta) = e^{i \theta} I
    #     $$
    #     """

    #     theta: ir.SSAValue = info.argument(types.Float)
    #     result: ir.ResultValue = info.result(OpType)

    # @interp.impl(op.stmts.ShiftOp)
    # def shiftop(
    #     self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.ShiftOp
    # ):
    #     """
    #     A phase shift operator.

    #     $$
    #     Shift(theta) = \\begin{bmatrix} 1 & 0 \\\\ 0 & e^{i \\theta} \\end{bmatrix}
    #     $$
    #     """

    #     theta: ir.SSAValue = info.argument(types.Float)
    #     result: ir.ResultValue = info.result(OpType)

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
    ):
        return (OperatorRuntime(method_name=stmt.name.lower()),)

    @interp.impl(op.stmts.P0)
    @interp.impl(op.stmts.P1)
    def projector(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: op.stmts.P0 | op.stmts.P1,
    ):
        state = isinstance(stmt, op.stmts.P1)
        return (ProjectorRuntime(to_state=state),)

    @interp.impl(op.stmts.Sn)
    def sn(self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.Sn):
        raise NotImplementedError()

    @interp.impl(op.stmts.Sp)
    def sp(self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: op.stmts.Sp):
        raise NotImplementedError()
