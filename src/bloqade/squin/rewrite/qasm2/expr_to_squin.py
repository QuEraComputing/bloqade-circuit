from math import pi

from kirin import ir
from kirin.dialects import py, math as kirin_math
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.qasm2.dialects.expr import stmts as expr_stmts

qasm2_binops = []


class QASM2ExprToSquin(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case expr_stmts.ConstInt() | expr_stmts.ConstFloat():
                return self.rewrite_Const(node)
            case expr_stmts.ConstPI():
                return self.rewrite_PI(node)
            case (
                expr_stmts.Mul()
                | expr_stmts.Add()
                | expr_stmts.Sub()
                | expr_stmts.Div()
                | expr_stmts.Pow()
            ):
                return self.rewrite_BinOp(node)
            case (
                expr_stmts.Neg()
                | expr_stmts.Sin()
                | expr_stmts.Cos()
                | expr_stmts.Tan()
                | expr_stmts.Exp()
                | expr_stmts.Log()
                | expr_stmts.Sqrt()
            ):
                return self.rewrite_UnaryOp(node)
            case _:
                return RewriteResult()

    def rewrite_Const(
        self, stmt: expr_stmts.ConstInt | expr_stmts.ConstFloat
    ) -> RewriteResult:

        py_const = py.Constant(value=stmt.value)
        stmt.replace_by(py_const)
        return RewriteResult(has_done_something=True)

    def rewrite_PI(self, stmt: expr_stmts.ConstPI) -> RewriteResult:

        py_const = py.Constant(value=pi)
        stmt.replace_by(py_const)
        return RewriteResult(has_done_something=True)

    def rewrite_BinOp(self, stmt: ir.Statement) -> RewriteResult:

        match stmt:
            case expr_stmts.Mul():
                op = py.binop.Mult
            case expr_stmts.Add():
                op = py.binop.Add
            case expr_stmts.Sub():
                op = py.binop.Sub
            case expr_stmts.Div():
                op = py.binop.Div
            case expr_stmts.Pow():
                op = py.binop.Pow
            case _:
                return RewriteResult()

        lhs = stmt.lhs
        rhs = stmt.rhs
        binop_expr = op(lhs=lhs, rhs=rhs)
        stmt.replace_by(binop_expr)
        return RewriteResult(has_done_something=True)

    def rewrite_UnaryOp(
        self,
        stmt: (
            expr_stmts.Neg
            | expr_stmts.Sin
            | expr_stmts.Cos
            | expr_stmts.Tan
            | expr_stmts.Exp
            | expr_stmts.Log
            | expr_stmts.Sqrt
        ),
    ) -> RewriteResult:

        match stmt:
            case expr_stmts.Neg():
                op = py.unary.stmts.USub
            case expr_stmts.Sin():
                op = kirin_math.stmts.sin
            case expr_stmts.Cos():
                op = kirin_math.stmts.cos
            case expr_stmts.Tan():
                op = kirin_math.stmts.tan
            case expr_stmts.Exp():
                op = kirin_math.stmts.exp
            case expr_stmts.Log():
                op = kirin_math.stmts.log2
            case expr_stmts.Sqrt():
                op = kirin_math.stmts.sqrt
            case _:
                return RewriteResult()

        value = stmt.value
        unary_expr = op(value)

        stmt.replace_by(unary_expr)
        return RewriteResult(has_done_something=True)
