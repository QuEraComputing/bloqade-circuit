from __future__ import annotations
from typing import Literal

from kirin import interp

from bloqade.qasm2.parse import ast
from bloqade.qasm2.emit import QASM2, Frame

from . import stmts
from ._dialect import dialect


@dialect.register(key="emit.qasm2")
class EmitExpr(interp.MethodTable):

    @interp.impl(stmts.ConstInt)
    @interp.impl(stmts.ConstFloat)
    def emit_const_int(
        self,
        emit: QASM2,
        frame: Frame,
        stmt: stmts.ConstInt | stmts.ConstFloat,
    ):
        return (ast.Number(stmt.value),)

    @interp.impl(stmts.ConstPI)
    def emit_const_pi(
        self,
        emit: QASM2,
        frame: Frame,
        stmt: stmts.ConstPI,
    ):
        return (ast.Pi(),)

    @interp.impl(stmts.Neg)
    def emit_neg(self, emit: QASM2, frame: Frame, stmt: stmts.Neg):
        arg = frame.get_casted(stmt.value, ast.Expr)
        return (ast.UnaryOp("-", arg),)

    @interp.impl(stmts.Sin)
    @interp.impl(stmts.Cos)
    @interp.impl(stmts.Tan)
    @interp.impl(stmts.Exp)
    @interp.impl(stmts.Log)
    @interp.impl(stmts.Sqrt)
    def emit_sin(self, emit: QASM2, frame: Frame, stmt):
        arg = frame.get_casted(stmt.value, ast.Expr)
        return (ast.Call(stmt.name, [arg]),)

    def emit_binop(
        self,
        sym: Literal["+", "-", "*", "/", "^"],
        emit: QASM2,
        frame: Frame,
        stmt,
    ):
        lhs = frame.get_casted(stmt.lhs, ast.Expr)
        rhs = frame.get_casted(stmt.rhs, ast.Expr)
        return (ast.BinOp(sym, lhs, rhs),)

    @interp.impl(stmts.Add)
    def emit_add(self, emit: QASM2, frame: Frame, stmt: stmts.Add):
        return self.emit_binop("+", emit, frame, stmt)

    @interp.impl(stmts.Sub)
    def emit_sub(self, emit: QASM2, frame: Frame, stmt: stmts.Add):
        return self.emit_binop("-", emit, frame, stmt)

    @interp.impl(stmts.Mul)
    def emit_mul(self, emit: QASM2, frame: Frame, stmt: stmts.Add):
        return self.emit_binop("*", emit, frame, stmt)

    @interp.impl(stmts.Div)
    def emit_div(self, emit: QASM2, frame: Frame, stmt: stmts.Add):
        return self.emit_binop("/", emit, frame, stmt)

    @interp.impl(stmts.Pow)
    def emit_pow(self, emit: QASM2, frame: Frame, stmt: stmts.Add):
        return self.emit_binop("^", emit, frame, stmt)
