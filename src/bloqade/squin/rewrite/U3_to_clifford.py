# create rewrite rule name SquinMeasureToStim using kirin
import math
from typing import List, Tuple, Callable

import numpy as np
from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin import op, qubit


def sdag() -> list[ir.Statement]:
    return [_op := op.stmts.S(), op.stmts.Adjoint(op=_op.result, is_unitary=True)]


# (theta, phi, lam)
U3_HALF_PI_ANGLE_TO_GATES: dict[
    tuple[int, int, int], Callable[[], Tuple[List[ir.Statement], ...]]
] = {
    (0, 0, 0): lambda: ([op.stmts.Identity(sites=1)],),
    (0, 0, 1): lambda: ([op.stmts.S()],),
    (0, 0, 2): lambda: ([op.stmts.Z()],),
    (0, 0, 3): lambda: (sdag(),),
    (1, 0, 0): lambda: ([op.stmts.SqrtY()],),
    (1, 0, 1): lambda: ([op.stmts.S()], [op.stmts.SqrtY()]),
    (1, 0, 2): lambda: ([op.stmts.H()],),
    (1, 0, 3): lambda: (sdag(), [op.stmts.SqrtY()]),
    (1, 1, 0): lambda: ([op.stmts.SqrtY()], [op.stmts.S()]),
    (1, 1, 1): lambda: ([op.stmts.S()], [op.stmts.SqrtY()], [op.stmts.S()]),
    (1, 1, 2): lambda: ([op.stmts.Z()], [op.stmts.SqrtY()], [op.stmts.S()]),
    (1, 1, 3): lambda: (sdag(), [op.stmts.SqrtY()], [op.stmts.S()]),
    (1, 2, 0): lambda: ([op.stmts.SqrtY()], [op.stmts.Z()]),
    (1, 2, 1): lambda: ([op.stmts.S()], [op.stmts.SqrtY()], [op.stmts.Z()]),
    (1, 2, 2): lambda: ([op.stmts.Z()], [op.stmts.SqrtY()], [op.stmts.Z()]),
    (1, 2, 3): lambda: (sdag(), [op.stmts.SqrtY()], [op.stmts.Z()]),
    (1, 3, 0): lambda: ([op.stmts.SqrtY()], sdag()),
    (1, 3, 1): lambda: ([op.stmts.S()], [op.stmts.SqrtY()], sdag()),
    (1, 3, 2): lambda: ([op.stmts.Z()], [op.stmts.SqrtY()], sdag()),
    (1, 3, 3): lambda: (sdag(), [op.stmts.SqrtY()], sdag()),
    (2, 0, 0): lambda: ([op.stmts.Y()],),
    (2, 0, 1): lambda: ([op.stmts.S()], [op.stmts.Y()]),
    (2, 0, 2): lambda: ([op.stmts.Z()], [op.stmts.Y()]),
    (2, 0, 3): lambda: (sdag(), [op.stmts.Y()]),
}


def equivalent_u3_para(
    theta_half_pi: int, phi_half_pi: int, lam_half_pi: int
) -> tuple[int, int, int]:
    """
    1. Assume all three angles are in the range [0, 4].
    2. U3(theta, phi, lam) = -U3(2pi-theta, phi+pi, lam+pi).
    """
    return ((4 - theta_half_pi) % 4, (phi_half_pi + 2) % 4, (lam_half_pi + 2) % 4)


class SquinU3ToClifford(RewriteRule):
    """
    Rewrite squin U3 statements to clifford when possible.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if isinstance(node, (qubit.Apply, qubit.Broadcast)):
            return self.rewrite_ApplyOrBroadcast_onU3(node)
        else:
            return RewriteResult()

    def get_constant(self, node: ir.SSAValue) -> float | None:
        if isinstance(node.owner, py.Constant):
            # node.value is a PyAttr, need to get the wrapped value out
            return node.owner.value.unwrap()
        else:
            return None

    def resolve_angle(self, angle: float) -> int | None:
        """
        Normalize the angle to be in the range [0, 2π).
        """
        # convert to 0.0~1.0, in unit of pi/2
        angle_half_pi = angle / math.pi * 2.0

        mod = angle_half_pi % 1.0
        if not (np.isclose(mod, 0.0) or np.isclose(mod, 1.0)):
            return None

        else:
            return round((angle / math.tau) % 1 * 4) % 4

    def rewrite_ApplyOrBroadcast_onU3(
        self, node: qubit.Apply | qubit.Broadcast
    ) -> RewriteResult:
        """
        Rewrite Apply and Broadcast nodes to their clifford equivalent statements.
        """
        if not isinstance(node.operator.owner, op.stmts.U3):
            return RewriteResult()

        gates = self.decompose_U3_gates(node.operator.owner)

        if len(gates) == 0:
            return RewriteResult()

        for stmt_list in gates:
            for gate_stmt in stmt_list[:-1]:
                gate_stmt.insert_before(node)

            oper = stmt_list[-1]
            oper.insert_before(node)
            new_node = node.__class__(operator=oper.result, qubits=node.qubits)
            new_node.insert_before(node)

        node.delete()

        # rewrite U3 to clifford gates
        return RewriteResult(has_done_something=True)

    def decompose_U3_gates(self, node: op.stmts.U3) -> Tuple[List[ir.Statement], ...]:
        """
        Rewrite U3 statements to clifford gates if possible.
        """
        theta = self.get_constant(node.theta)
        phi = self.get_constant(node.phi)
        lam = self.get_constant(node.lam)

        if theta is None or phi is None or lam is None:
            return ()

        theta_half_pi: int | None = self.resolve_angle(theta)
        phi_half_pi: int | None = self.resolve_angle(phi)
        lam_half_pi: int | None = self.resolve_angle(lam)

        if theta_half_pi is None or phi_half_pi is None or lam_half_pi is None:
            return ()

        angles_key = (theta_half_pi, phi_half_pi, lam_half_pi)
        if angles_key not in U3_HALF_PI_ANGLE_TO_GATES:
            angles_key = equivalent_u3_para(*angles_key)
            if angles_key not in U3_HALF_PI_ANGLE_TO_GATES:
                return ()

        gates_stmts = U3_HALF_PI_ANGLE_TO_GATES.get(angles_key)

        # no consistent gates, then:
        assert (
            gates_stmts is not None
        ), "internal error, U3 gates not found for angles: {}".format(angles_key)

        return gates_stmts()
