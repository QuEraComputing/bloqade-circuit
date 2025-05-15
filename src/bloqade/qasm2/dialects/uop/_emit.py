from __future__ import annotations
from kirin import interp

from bloqade.qasm2.parse import ast
from bloqade.qasm2.emit import QASM2, Frame

from . import stmts
from ._dialect import dialect


@dialect.register(key="emit.qasm2")
class UOp(interp.MethodTable):

    @interp.impl(stmts.CX)
    def emit_cx(
        self,
        emit: QASM2,
        frame: Frame,
        stmt: stmts.CX,
    ):
        ctrl = frame.get_casted(stmt.ctrl, (ast.Bit, ast.Name))
        qarg = frame.get_casted(stmt.qarg, (ast.Bit, ast.Name))
        frame.body.append(ast.CXGate(ctrl=ctrl, qarg=qarg))
        return ()

    @interp.impl(stmts.UGate)
    def emit_ugate(
        self,
        emit: QASM2,
        frame: Frame,
        stmt: stmts.UGate,
    ):
        theta = frame.get_casted(stmt.theta, ast.Expr)
        phi = frame.get_casted(stmt.phi, ast.Expr)
        lam = frame.get_casted(stmt.lam, ast.Expr)
        qarg = frame.get_casted(stmt.qarg, (ast.Bit, ast.Name))
        frame.body.append(ast.UGate(theta=theta, phi=phi, lam=lam, qarg=qarg))
        return ()

    @interp.impl(stmts.Barrier)
    def emit_barrier(
        self,
        emit: QASM2,
        frame: Frame,
        stmt: stmts.Barrier,
    ):
        qargs = [
            frame.get_casted(qarg, (ast.Bit, ast.Name))
            for qarg in stmt.qargs
        ]
        frame.body.append(ast.Barrier(qargs=qargs))
        return ()

    @interp.impl(stmts.SX)
    @interp.impl(stmts.SXdag)
    @interp.impl(stmts.Id)
    @interp.impl(stmts.H)
    @interp.impl(stmts.X)
    @interp.impl(stmts.Y)
    @interp.impl(stmts.Z)
    @interp.impl(stmts.S)
    @interp.impl(stmts.Sdag)
    @interp.impl(stmts.T)
    @interp.impl(stmts.Tdag)
    def emit_single_qubit_gate(
        self, emit: QASM2, frame: Frame, stmt: stmts.SingleQubitGate
    ):
        qarg = frame.get_casted(stmt.qarg, (ast.Bit, ast.Name))
        frame.body.append(
            ast.Instruction(name=ast.Name(stmt.name), params=[], qargs=[qarg])
        )
        return ()

    @interp.impl(stmts.RX)
    @interp.impl(stmts.RY)
    @interp.impl(stmts.RZ)
    def emit_rotation(
        self,
        emit: QASM2,
        frame: Frame,
        stmt: stmts.RX | stmts.RY | stmts.RZ,
    ):
        theta = frame.get_casted(stmt.theta, ast.Expr)
        qarg = frame.get_casted(stmt.qarg, (ast.Bit, ast.Name))
        frame.body.append(
            ast.Instruction(name=ast.Name(stmt.name), params=[theta], qargs=[qarg])
        )
        return ()

    @interp.impl(stmts.U1)
    def emit_u1(self, emit: QASM2, frame: Frame, stmt: stmts.U1):
        lam = frame.get_casted(stmt.lam, ast.Expr)
        qarg = frame.get_casted(stmt.qarg, (ast.Bit, ast.Name))
        frame.body.append(
            ast.Instruction(name=ast.Name(stmt.name), params=[lam], qargs=[qarg])
        )
        return ()

    @interp.impl(stmts.U2)
    def emit_u2(self, emit: QASM2, frame: Frame, stmt: stmts.U2):
        phi = frame.get_casted(stmt.phi, ast.Expr)
        lam = frame.get_casted(stmt.lam, ast.Expr)
        qarg = frame.get_casted(stmt.qarg, (ast.Bit, ast.Name))
        frame.body.append(
            ast.Instruction(name=ast.Name(stmt.name), params=[phi, lam], qargs=[qarg])
        )
        return ()

    @interp.impl(stmts.Swap)
    @interp.impl(stmts.CSX)
    @interp.impl(stmts.CZ)
    @interp.impl(stmts.CY)
    @interp.impl(stmts.CH)
    def emit_two_qubit_gate(
        self, emit: QASM2, frame: Frame, stmt: stmts.CZ
    ):
        ctrl = frame.get_casted(stmt.ctrl, (ast.Bit, ast.Name))
        qarg = frame.get_casted(stmt.qarg, (ast.Bit, ast.Name))
        frame.body.append(
            ast.Instruction(name=ast.Name(stmt.name), params=[], qargs=[ctrl, qarg])
        )
        return ()

    @interp.impl(stmts.CCX)
    def emit_ccx(self, emit: QASM2, frame: Frame, stmt: stmts.CCX):
        ctrl1 = frame.get_casted(stmt.ctrl1, (ast.Bit, ast.Name))
        ctrl2 = frame.get_casted(stmt.ctrl2, (ast.Bit, ast.Name))
        qarg = frame.get_casted(stmt.qarg, (ast.Bit, ast.Name))

        frame.body.append(
            ast.Instruction(
                name=ast.Name(stmt.name), params=[], qargs=[ctrl1, ctrl2, qarg]
            )
        )
        return ()

    @interp.impl(stmts.CSwap)
    def emit_cswap(self, emit: QASM2, frame: Frame, stmt: stmts.CSwap):
        ctrl = frame.get_casted(stmt.ctrl, (ast.Bit, ast.Name))
        qarg1 = frame.get_casted(stmt.qarg1, (ast.Bit, ast.Name))
        qarg2 = frame.get_casted(stmt.qarg2, (ast.Bit, ast.Name))

        frame.body.append(
            ast.Instruction(
                name=ast.Name(stmt.name), params=[], qargs=[ctrl, qarg1, qarg2]
            )
        )
        return ()

    @interp.impl(stmts.CRZ)
    @interp.impl(stmts.CRY)
    @interp.impl(stmts.CRX)
    def emit_cr(self, emit: QASM2, frame: Frame, stmt: stmts.CRX):
        lam = frame.get_casted(stmt.lam, ast.Expr)
        ctrl = frame.get_casted(stmt.ctrl, (ast.Bit, ast.Name))
        qarg = frame.get_casted(stmt.qarg, (ast.Bit, ast.Name))

        frame.body.append(
            ast.Instruction(name=ast.Name(stmt.name), params=[lam], qargs=[ctrl, qarg])
        )
        return ()

    @interp.impl(stmts.CU1)
    def emit_cu1(self, emit: QASM2, frame: Frame, stmt: stmts.CU1):
        lam = frame.get_casted(stmt.lam, ast.Expr)
        ctrl = frame.get_casted(stmt.ctrl, (ast.Bit, ast.Name))
        qarg = frame.get_casted(stmt.qarg, (ast.Bit, ast.Name))

        frame.body.append(
            ast.Instruction(name=ast.Name(stmt.name), params=[lam], qargs=[ctrl, qarg])
        )
        return ()

    @interp.impl(stmts.CU3)
    def emit_cu3(self, emit: QASM2, frame: Frame, stmt: stmts.CU3):
        theta = frame.get_casted(stmt.theta, ast.Expr)
        phi = frame.get_casted(stmt.phi, ast.Expr)
        lam = frame.get_casted(stmt.lam, ast.Expr)
        ctrl = frame.get_casted(stmt.ctrl, (ast.Bit, ast.Name))
        qarg = frame.get_casted(stmt.qarg, (ast.Bit, ast.Name))

        frame.body.append(
            ast.Instruction(
                name=ast.Name(stmt.name), params=[theta, phi, lam], qargs=[ctrl, qarg]
            )
        )
        return ()

    @interp.impl(stmts.CU)
    def emit_cu(self, emit: QASM2, frame: Frame, stmt: stmts.CU):
        theta = frame.get_casted(stmt.theta, ast.Expr)
        phi = frame.get_casted(stmt.phi, ast.Expr)
        lam = frame.get_casted(stmt.lam, ast.Expr)
        gamma = frame.get_casted(stmt.gamma, ast.Expr)
        ctrl = frame.get_casted(stmt.ctrl, (ast.Bit, ast.Name))
        qarg = frame.get_casted(stmt.qarg, (ast.Bit, ast.Name))
        
        frame.body.append(
            ast.Instruction(
                name=ast.Name(stmt.name),
                params=[theta, phi, lam, gamma],
                qargs=[ctrl, qarg],
            )
        )
        return ()

    @interp.impl(stmts.RZZ)
    @interp.impl(stmts.RXX)
    def emit_r2q(self, emit: QASM2, frame: Frame, stmt: stmts.RZZ):
        theta = frame.get_casted(stmt.theta, ast.Expr)
        ctrl = frame.get_casted(stmt.ctrl, (ast.Bit, ast.Name))
        qarg = frame.get_casted(stmt.qarg, (ast.Bit, ast.Name))

        frame.body.append(
            ast.Instruction(
                name=ast.Name(stmt.name), params=[theta], qargs=[ctrl, qarg]
            )
        )
        return ()
