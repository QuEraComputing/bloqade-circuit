from __future__ import annotations

from kirin import interp

from bloqade.qasm2.parse import ast
from bloqade.qasm2.emit import QASM2, Frame

from . import stmts
from ._dialect import dialect


@dialect.register(key="emit.qasm2")
class Core(interp.MethodTable):

    @interp.impl(stmts.CRegNew)
    def emit_creg_new(
        self, emit: QASM2, frame: Frame, stmt: stmts.CRegNew
    ):
        n_bits = frame.get_casted(stmt.n_bits, ast.Number)
        # check if its int first, because Int.is_integer() is added for >=3.12
        assert isinstance(n_bits.value, int), "expected integer"
        name = frame.ssa[stmt.result]
        frame.body.append(ast.CReg(name=name, size=int(n_bits.value)))
        return (ast.Name(name),)

    @interp.impl(stmts.QRegNew)
    def emit_qreg_new(
        self, emit: QASM2, frame: Frame, stmt: stmts.QRegNew
    ):
        n_bits = frame.get_casted(stmt.n_qubits, ast.Number)
        assert isinstance(n_bits.value, int), "expected integer"
        name = frame.ssa[stmt.result]
        frame.body.append(ast.QReg(name=name, size=int(n_bits.value)))
        return (ast.Name(name),)

    @interp.impl(stmts.Reset)
    def emit_reset(self, emit: QASM2, frame: Frame, stmt: stmts.Reset):
        qarg: ast.Name | ast.Bit = frame.get(stmt.qarg) # type: ignore
        frame.body.append(ast.Reset(qarg=qarg))
        return ()

    @interp.impl(stmts.Measure)
    def emit_measure(
        self, emit: QASM2, frame: Frame, stmt: stmts.Measure
    ):
        qarg: ast.Bit | ast.Name = frame.get(stmt.qarg) # type: ignore
        carg: ast.Name | ast.Bit = frame.get(stmt.carg) # type: ignore
        frame.body.append(ast.Measure(qarg=qarg, carg=carg))
        return ()

    @interp.impl(stmts.CRegEq)
    def emit_creg_eq(
        self, emit: QASM2, frame: Frame, stmt: stmts.CRegEq
    ):
        lhs = frame.get_casted(stmt.lhs, ast.Expr)
        rhs = frame.get_casted(stmt.rhs, ast.Expr)
        return (ast.Cmp(lhs=lhs, rhs=rhs),)

    @interp.impl(stmts.CRegGet)
    @interp.impl(stmts.QRegGet)
    def emit_qreg_get(
        self,
        emit: QASM2,
        frame: Frame,
        stmt: stmts.QRegGet | stmts.CRegGet,
    ):
        reg = frame.get_casted(stmt.reg, ast.Name)
        idx = frame.get_casted(stmt.idx, ast.Number)
        assert isinstance(idx.value, int)
        return (ast.Bit(reg, int(idx.value)),)
