import math
from typing import TypeVar

from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from .. import op

# NOTE: generic type used below, bound to guarantee a .result field
_T = TypeVar("_T", bound=py.Constant | py.USub | py.Mult | op.stmts.Operator)


class PhasedXZToRotations(RewriteRule):
    """
    Decompose a PhasedXZ gate into rotation statements.

    PhasedXZ is defined as

    $$
    Z^z Z^a X^x Z^{-a}
    $$

    which we can rewrite as

    $$
    R_z(z \\pi) R_z(a \\pi) R_x(x \\pi) R_z(-a \\pi)
    $$
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        if not isinstance(node, op.stmts.PhasedXZ):
            return RewriteResult()

        def insert_and_return(stmt: _T) -> ir.ResultValue:
            node.insert_before(stmt)
            return stmt.result

        axis_exponent = node.axis_exponent
        x_exponent = node.x_exponent
        z_exponent = node.z_exponent

        # NOTE: compute the angles
        pi = insert_and_return(py.Constant(math.pi))
        axis_angle = insert_and_return(py.Mult(axis_exponent, pi))
        neg_axis_angle = insert_and_return(py.USub(axis_angle))
        x_angle = insert_and_return(py.Mult(x_exponent, pi))
        z_angle = insert_and_return(py.Mult(z_exponent, pi))

        x = insert_and_return(op.stmts.X())
        z = insert_and_return(op.stmts.Z())

        # NOTE: define the rotations
        rz_a = insert_and_return(op.stmts.Rot(axis=z, angle=axis_angle))
        rz_neg_a = insert_and_return(op.stmts.Rot(axis=z, angle=neg_axis_angle))
        rz_z = insert_and_return(op.stmts.Rot(axis=z, angle=z_angle))
        rx = insert_and_return(op.stmts.Rot(axis=x, angle=x_angle))

        # NOTE: split into two multiplications
        m_lhs = insert_and_return(op.stmts.Mult(rz_z, rz_a))
        m_rhs = insert_and_return(op.stmts.Mult(rx, rz_neg_a))

        # NOTE: final result is a multiplication of the two multiplications above
        new_node = op.stmts.Mult(m_lhs, m_rhs)
        node.replace_by(new_node)

        return RewriteResult(has_done_something=True)
