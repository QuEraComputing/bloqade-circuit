# create rewrite rule name SquinMeasureToStim using kirin
import math

import numpy as np
from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin import op


class SquinU3ToClifford(RewriteRule):
    """
    Rewrite squin U3 statements to clifford when possible.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if isinstance(node, op.stmts.U3):
            return self.rewrite_U3(node)
        else:
            return RewriteResult()

    def get_constant(self, node: ir.SSAValue) -> float | None:
        if isinstance(node.owner, py.Constant):
            # node.value is a PyAttr, need to get the wrapped value out
            return node.owner.value.unwrap()
        else:
            return None

    def resolve_new_stmt(self, theta_2pi, phi_2pi, lam_2pi) -> ir.Statement | None:

        # make it from 0.0~1.0
        theta_2pi = theta_2pi % 1.0
        phi_2pi = phi_2pi % 1.0
        lam_2pi = lam_2pi % 1.0

        # Check if the U3 gate can be rewritten as a Clifford gate
        if np.isclose(theta_2pi, 0.5):
            # X or Y
            if np.isclose(phi_2pi, 0.0) and np.isclose(lam_2pi, 0.5):
                return op.stmts.X()
            elif np.isclose(phi_2pi, 0.25) and np.isclose(lam_2pi, 0.25):
                return op.stmts.Y()

        elif np.isclose(theta_2pi, 0.0) and np.isclose(phi_2pi, 0.0):
            # u1: z or s or sdg
            if np.isclose(lam_2pi, 0.5):
                return op.stmts.Z()
            elif np.isclose(lam_2pi, 0.25):
                return op.stmts.S()
            elif np.isclose(lam_2pi, 0.75):
                s1 = op.stmts.S()
                s2 = op.stmts.Adjoint(op=s1.result, is_unitary=True)
                return s2
            elif np.isclose(lam_2pi, 0.0) or np.isclose(lam_2pi, 1.0):
                return op.stmts.Identity(sites=1)

        elif (
            np.isclose(theta_2pi, 0.25)
            and np.isclose(phi_2pi, 0.0)
            and np.isclose(lam_2pi, 0.5)
        ):
            return op.stmts.H()

        return None

    def rewrite_U3(self, node: op.stmts.U3) -> RewriteResult:
        """
        Rewrite U3 statements to clifford gates if possible.
        """
        theta = self.get_constant(node.theta)
        phi = self.get_constant(node.phi)
        lam = self.get_constant(node.lam)

        if theta is None or phi is None or lam is None:
            return RewriteResult()

        new_stmt = self.resolve_new_stmt(
            theta / math.tau, phi / math.tau, lam / math.tau
        )
        if new_stmt is None:
            return RewriteResult()

        node.replace_by(new_stmt)
        return RewriteResult(has_done_something=True)
