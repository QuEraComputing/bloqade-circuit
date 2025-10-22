# create rewrite rule name SquinMeasureToStim using kirin
import math

import numpy as np
from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin import gate


# Placeholder type, swap in an actual S statement with adjoint=True
# during the rewrite method
class Sdag(ir.Statement):
    pass


class SqrtXdag(ir.Statement):
    pass


class SqrtYdag(ir.Statement):
    pass


# (theta, phi, lam)
U3_HALF_PI_ANGLE_TO_GATES: dict[
    tuple[int, int, int], list[type[ir.Statement]] | list[None]
] = {
    (0, 0, 0): [None],
    (0, 0, 1): [gate.stmts.S],
    (0, 0, 2): [gate.stmts.Z],
    (0, 0, 3): [Sdag],
    (1, 0, 0): [gate.stmts.SqrtY],
    (1, 0, 1): [gate.stmts.S, gate.stmts.SqrtY],
    (1, 0, 2): [gate.stmts.Z, gate.stmts.SqrtY],
    (1, 0, 3): [Sdag, gate.stmts.SqrtY],
    (1, 1, 0): [gate.stmts.S, SqrtXdag],
    (1, 1, 1): [gate.stmts.Z, SqrtXdag],
    (1, 1, 2): [Sdag, SqrtXdag],
    (1, 1, 3): [SqrtXdag],
    (1, 2, 0): [gate.stmts.Z, SqrtYdag],
    (1, 2, 1): [Sdag, SqrtYdag],
    (1, 2, 2): [SqrtYdag],
    (1, 2, 3): [gate.stmts.S, SqrtYdag],
    (1, 3, 0): [Sdag, gate.stmts.SqrtX],
    (1, 3, 1): [gate.stmts.SqrtX],
    (1, 3, 2): [gate.stmts.S, gate.stmts.SqrtX],
    (1, 3, 3): [gate.stmts.Z, gate.stmts.SqrtX],
    (2, 0, 0): [gate.stmts.Y],
    (2, 0, 1): [gate.stmts.S, gate.stmts.Y],
    (2, 0, 2): [gate.stmts.X],
    (2, 0, 3): [Sdag, gate.stmts.Y],
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
        if isinstance(node, gate.stmts.U3):
            return self.rewrite_U3(node)
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

    def rewrite_U3(self, node: gate.stmts.U3) -> RewriteResult:
        """
        Rewrite Apply and Broadcast nodes to their clifford equivalent statements.
        """

        gates = self.decompose_U3_gates(node)

        if len(gates) == 0:
            return RewriteResult()

        # Get rid of the U3 gate altogether if it's identity
        if len(gates) == 1 and gates[0] is None:
            node.delete()
            return RewriteResult(has_done_something=True)

        for gate_stmt in gates:
            if gate_stmt is Sdag:
                new_stmt = gate.stmts.S(adjoint=True, qubits=node.qubits)
            if gate_stmt is SqrtXdag:
                new_stmt = gate.stmts.SqrtX(adjoint=True, qubits=node.qubits)
            if gate_stmt is SqrtYdag:
                new_stmt = gate.stmts.SqrtY(adjoint=True, qubits=node.qubits)
            else:
                new_stmt = gate_stmt(qubits=node.qubits)
            new_stmt.insert_before(node)

        node.delete()

        return RewriteResult(has_done_something=True)

    def decompose_U3_gates(
        self, node: gate.stmts.U3
    ) -> list[type[ir.Statement]] | list[None]:
        """
        Rewrite U3 statements to clifford gates if possible.
        """
        theta = self.get_constant(node.theta)
        phi = self.get_constant(node.phi)
        lam = self.get_constant(node.lam)

        if theta is None or phi is None or lam is None:
            return []

        # Angles will be in units of turns, we convert to radians
        # to allow for the old logic to work
        theta = theta * math.tau
        phi = phi * math.tau
        lam = lam * math.tau

        # For U3(2*pi*n, phi, lam) = U3(0, 0, lam + phi) which is a Z rotation.
        if np.isclose(np.mod(theta, math.tau), 0):
            lam = lam + phi
            phi = 0.0
        elif np.isclose(np.mod(theta + np.pi, math.tau), 0):
            lam = lam - phi
            phi = 0.0

        theta_half_pi: int | None = self.resolve_angle(theta)
        phi_half_pi: int | None = self.resolve_angle(phi)
        lam_half_pi: int | None = self.resolve_angle(lam)

        if theta_half_pi is None or phi_half_pi is None or lam_half_pi is None:
            return []

        angles_key = (theta_half_pi, phi_half_pi, lam_half_pi)
        if angles_key not in U3_HALF_PI_ANGLE_TO_GATES:
            angles_key = equivalent_u3_para(*angles_key)
            if angles_key not in U3_HALF_PI_ANGLE_TO_GATES:
                return []

        gates_stmts = U3_HALF_PI_ANGLE_TO_GATES.get(angles_key)

        # no consistent gates, then:
        assert (
            gates_stmts is not None
        ), "internal error, U3 gates not found for angles: {}".format(angles_key)

        return gates_stmts
