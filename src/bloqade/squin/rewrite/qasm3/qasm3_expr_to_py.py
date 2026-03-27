"""Rewrite QASM3 expression dialect statements into py/math dialect equivalents."""

import math as pymath

from kirin import ir
from kirin.dialects import py, math
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.qasm3.dialects import expr


class QASM3ExprToPy(RewriteRule):
    """
    Rewrite QASM3 expression statements to their py/math dialect equivalents.

    This mirrors the QASM2Py rewrite rule but for the QASM3 expression dialect.
    """

    UNARY_OPS: dict[type[ir.Statement], type[ir.Statement]] = {
        expr.Neg: py.USub,
        expr.Sin: math.stmts.sin,
        expr.Cos: math.stmts.cos,
        expr.Tan: math.stmts.tan,
        expr.Exp: math.stmts.exp,
        expr.Sqrt: math.stmts.sqrt,
    }

    BINARY_OPS: dict[type[ir.Statement], type[ir.Statement]] = {
        expr.Add: py.Add,
        expr.Sub: py.Sub,
        expr.Mul: py.Mult,
        expr.Div: py.Div,
        expr.Pow: py.Pow,
    }

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if isinstance(node, (expr.ConstInt, expr.ConstFloat)):
            node.replace_by(py.Constant(value=node.value))
            return RewriteResult(has_done_something=True)
        elif isinstance(node, expr.ConstPI):
            node.replace_by(py.Constant(value=pymath.pi))
            return RewriteResult(has_done_something=True)
        elif isinstance(node, expr.Neg):
            node.replace_by(self.UNARY_OPS[type(node)](value=node.value))
            return RewriteResult(has_done_something=True)
        elif isinstance(node, (expr.Sin, expr.Cos, expr.Tan, expr.Exp, expr.Sqrt)):
            node.replace_by(self.UNARY_OPS[type(node)](x=node.value))
            return RewriteResult(has_done_something=True)
        elif isinstance(node, (expr.Add, expr.Sub, expr.Mul, expr.Div, expr.Pow)):
            node.replace_by(self.BINARY_OPS[type(node)](lhs=node.lhs, rhs=node.rhs))
            return RewriteResult(has_done_something=True)
        else:
            return RewriteResult()
