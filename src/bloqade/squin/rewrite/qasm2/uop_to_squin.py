from math import pi

from kirin import ir
from kirin.dialects import py, func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.qasm2.dialects.uop import stmts as uop_stmts


# assume that qasm2.core conversion has already run beforehand
class QASM2UOPToSquin(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case uop_stmts.CX() | uop_stmts.CZ() | uop_stmts.CY():
                return self.rewrite_TwoQubitCtrlGate(node)
            case (
                uop_stmts.X()
                | uop_stmts.Y()
                | uop_stmts.Z()
                | uop_stmts.H()
                | uop_stmts.S()
                | uop_stmts.T()
                | uop_stmts.SX()
            ):
                return self.rewrite_SingleQubitGate_no_parameters(node)
            case uop_stmts.RZ() | uop_stmts.RX() | uop_stmts.RY():
                return self.rewrite_SingleQubit_with_parameters(node)
            case uop_stmts.UGate() | uop_stmts.U1() | uop_stmts.U2():
                return self.rewrite_u_gates(node)
            case uop_stmts.Id():
                return self.rewrite_Id(node)
            case _:
                return RewriteResult()

    def rewrite_TwoQubitCtrlGate(
        self, stmt: uop_stmts.CX | uop_stmts.CZ | uop_stmts.CY
    ) -> RewriteResult:

        # qasm2 does not have broadcast semantics
        # don't have to worry about these being lists
        carg = stmt.ctrl
        qarg = stmt.qarg

        match stmt:
            case uop_stmts.CX():
                squin_2q_stdlib = squin.cx
            case uop_stmts.CZ():
                squin_2q_stdlib = squin.cz
            case uop_stmts.CY():
                squin_2q_stdlib = squin.cy
            case _:
                return RewriteResult()

        invoke_stmt = func.Invoke(
            callee=squin_2q_stdlib,
            inputs=(carg, qarg),
        )

        stmt.replace_by(invoke_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_SingleQubitGate_no_parameters(
        self,
        stmt: (
            uop_stmts.X
            | uop_stmts.Y
            | uop_stmts.Z
            | uop_stmts.H
            | uop_stmts.S
            | uop_stmts.T
        ),
    ) -> RewriteResult:

        qarg = stmt.qarg
        match stmt:
            case uop_stmts.X():
                squin_1q_stdlib = squin.x
            case uop_stmts.Y():
                squin_1q_stdlib = squin.y
            case uop_stmts.Z():
                squin_1q_stdlib = squin.z
            case uop_stmts.H():
                squin_1q_stdlib = squin.h
            case uop_stmts.S():
                squin_1q_stdlib = squin.s
            case uop_stmts.T():
                squin_1q_stdlib = squin.t
            case uop_stmts.SX():
                squin_1q_stdlib = squin.sqrt_x
            case _:
                return RewriteResult()

        invoke_stmt = func.Invoke(
            callee=squin_1q_stdlib,
            inputs=(qarg,),
        )

        stmt.replace_by(invoke_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_u_gates(
        self, stmt: uop_stmts.UGate | uop_stmts.U1 | uop_stmts.U2
    ) -> RewriteResult:

        match stmt:
            case uop_stmts.UGate(lam=lam, phi=phi, theta=theta, qarg=qarg):
                args = (theta, phi, lam, qarg)
            case uop_stmts.U1(lam=lam, qarg=qarg):
                zero_stmt = py.Constant(value=0.0)
                zero_stmt.insert_before(stmt)
                args = (zero_stmt.result, zero_stmt.result, lam, qarg)
            case uop_stmts.U2(phi=phi, lam=lam, qarg=qarg):
                half_pi_stmt = py.Constant(value=pi / 2)
                half_pi_stmt.insert_before(stmt)
                args = (half_pi_stmt.result, phi, lam, qarg)
            case _:
                return RewriteResult()

        invoke_stmt = func.Invoke(
            callee=squin.u3,
            inputs=args,
        )

        stmt.replace_by(invoke_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_SingleQubit_with_parameters(
        self, stmt: uop_stmts.RZ | uop_stmts.RX | uop_stmts.RY
    ) -> RewriteResult:

        qarg = stmt.qarg
        theta = stmt.theta

        match stmt:
            case uop_stmts.RZ():
                squin_1q_stdlib = squin.rz
            case uop_stmts.RX():
                squin_1q_stdlib = squin.rx
            case uop_stmts.RY():
                squin_1q_stdlib = squin.ry
            case _:
                return RewriteResult()

        invoke_stmt = func.Invoke(
            callee=squin_1q_stdlib,
            inputs=(theta, qarg),
        )

        stmt.replace_by(invoke_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_Id(self, stmt: uop_stmts.Id) -> RewriteResult:

        # Identity does not exist in squin,
        # we can just remove it from the program

        stmt.delete()

        return RewriteResult(has_done_something=True)
