import numpy as np
from kirin import ir
from kirin.rewrite import abc as rewrite_abc
from kirin.dialects import py

from bloqade.squin.gate import stmts as gate_stmts


class RewriteMergeU3(rewrite_abc.RewriteRule):
    """Merge consecutive U3 gates on the same qubit into a single U3 gate.

    This rewrite rule identifies sequences of consecutive U3 gates applied to the same qubit and merges them into a single U3 gate that is equivalent to the combined effect of the original gates. It does not take into account commutation rules with other gates.

    Currently this is realized by explicitly computing the matrix multiplication of the two U3 gates and extracting the resulting U3 parameters. This only works if the U3 parameters are constants.
    """

    rounded_decimals = 10  # number of decimals to round to avoid numerical issues

    def rewrite_Statement(self, node: ir.Statement) -> rewrite_abc.RewriteResult:
        if not isinstance(node, gate_stmts.U3):
            return rewrite_abc.RewriteResult()

        if not isinstance(node.next_stmt, gate_stmts.U3):
            return rewrite_abc.RewriteResult()

        # general case: compute matrix multiplication of U3 gates
        lam_ssa = node.lam
        lam: float | None = None
        if isinstance(lam_ssa.owner, py.Constant):
            lam = lam_ssa.owner.value.unwrap()
        phi_ssa = node.phi
        phi: float | None = None
        if isinstance(phi_ssa.owner, py.Constant):
            phi = phi_ssa.owner.value.unwrap()
        theta_ssa = node.theta
        theta: float | None = None
        if isinstance(theta_ssa.owner, py.Constant):
            theta = theta_ssa.owner.value.unwrap()

        next_stmt = node.next_stmt
        next_lam_ssa = next_stmt.lam
        next_lam: float | None = None
        if isinstance(next_lam_ssa.owner, py.Constant):
            next_lam = next_lam_ssa.owner.value.unwrap()
        next_phi_ssa = next_stmt.phi
        next_phi: float | None = None
        if isinstance(next_phi_ssa.owner, py.Constant):
            next_phi = next_phi_ssa.owner.value.unwrap()
        next_theta_ssa = next_stmt.theta
        next_theta: float | None = None
        if isinstance(next_theta_ssa.owner, py.Constant):
            next_theta = next_theta_ssa.owner.value.unwrap()

        if (
            lam is None
            or phi is None
            or theta is None
            or next_lam is None
            or next_phi is None
            or next_theta is None
        ):
            return rewrite_abc.RewriteResult()

        # compute combined matrix
        def u3(theta: float, phi: float, lam: float) -> np.ndarray:
            theta *= 2 * np.pi
            phi *= 2 * np.pi
            lam *= 2 * np.pi
            return np.array(
                [
                    [
                        np.cos(theta / 2),
                        -np.exp(1j * lam) * np.sin(theta / 2),
                    ],
                    [
                        np.exp(1j * phi) * np.sin(theta / 2),
                        np.exp(1j * (phi + lam)) * np.cos(theta / 2),
                    ],
                ]
            )

        new_u3 = u3(next_theta, next_phi, next_lam) @ u3(theta, phi, lam)
        # normalize to U(2) by removing global phase and extract new parameters
        gamma = 0.5 * np.angle(np.linalg.det(new_u3))
        new_u3 *= np.exp(-1j * gamma)
        new_theta = round(
            float(
                2 * np.arctan2(np.abs(new_u3[0, 1]), np.abs(new_u3[0, 0])) / (2 * np.pi)
            ),
            self.rounded_decimals,
        )
        new_phi = round(
            float(np.angle(new_u3[1, 0]) / (2 * np.pi)), self.rounded_decimals
        )
        new_lam = round(
            float(np.angle(-new_u3[0, 1]) / (2 * np.pi)), self.rounded_decimals
        )

        # check that the computed parameters yield the same matrix
        assert np.allclose(
            new_u3,
            u3(new_theta, new_phi, new_lam),
        ), "Computed U3 parameters do not match the resulting matrix"

        # insert new constants and replace node
        theta_stmt = py.Constant(new_theta)
        phi_stmt = py.Constant(new_phi)
        lam_stmt = py.Constant(new_lam)
        theta_stmt.insert_before(node)
        phi_stmt.insert_before(node)
        lam_stmt.insert_before(node)

        node.replace_by(
            gate_stmts.U3(
                qubits=node.qubits,
                theta=theta_stmt.result,
                phi=phi_stmt.result,
                lam=lam_stmt.result,
            )
        )
        next_stmt.delete()

        return rewrite_abc.RewriteResult()
