"""Rewrite py.binop.mult to Mult stmt"""

from kirin import ir
from kirin.passes import Pass
from kirin.rewrite import Walk
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from .stmts import Mult, Scale
from .types import OpType


class _PyMultToSquinMult(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, py.Mult):
            return RewriteResult()

        lhs_is_op = node.lhs.type.is_subseteq(OpType)
        rhs_is_op = node.rhs.type.is_subseteq(OpType)

        if not lhs_is_op and not rhs_is_op:
            return RewriteResult()

        if lhs_is_op and rhs_is_op:
            mult = Mult(node.lhs, node.rhs)
            node.replace_by(mult)
            return RewriteResult(has_done_something=True)

        if lhs_is_op:
            scale = Scale(node.lhs, node.rhs)
            node.replace_by(scale)
            return RewriteResult(has_done_something=True)

        if rhs_is_op:
            scale = Scale(node.rhs, node.lhs)
            node.replace_by(scale)
            return RewriteResult(has_done_something=True)

        return RewriteResult()


class PyMultToSquinMult(Pass):

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        return Walk(_PyMultToSquinMult()).rewrite(mt.code)
