from kirin import ir
from kirin.rewrite import abc as rewrite_abc
from kirin.dialects import py

from bloqade.squin.gate import stmts as gate_stmts


class RewriteNonCliffordToU3(rewrite_abc.RewriteRule):
    """Rewrite non-Clifford gates to U3 gates.

    This rewrite rule transforms specific non-Clifford single-qubit gates
    into equivalent U3 gate representations. The following transformations are applied:
    - T gate (with adjoint attribute) to U3 gate with parameters (0, 0, ±π/4)
    - Rx gate to U3 gate with parameters (angle, -π/2, π/2)
    - Ry gate to U3 gate with parameters (angle, 0, 0)
    - Rz gate is U3 gate with parameters (0, 0, angle)

    This rewrite should be paired with `U3ToClifford` to canonicalize the circuit.

    """

    def rewrite_Statement(self, node: ir.Statement) -> rewrite_abc.RewriteResult:
        if not isinstance(
            node,
            (
                gate_stmts.T,
                gate_stmts.Rx,
                gate_stmts.Ry,
                gate_stmts.Rz,
            ),
        ):
            return rewrite_abc.RewriteResult()

        rule = getattr(self, f"rewrite_{type(node).__name__}")

        return rule(node)

    def rewrite_T(self, node: gate_stmts.T) -> rewrite_abc.RewriteResult:
        if node.adjoint:
            lam_value = -1.0 / 8.0
        else:
            lam_value = 1.0 / 8.0

        (theta_stmt := py.Constant(0.0)).insert_before(node)
        (phi_stmt := py.Constant(0.0)).insert_before(node)
        (lam_stmt := py.Constant(lam_value)).insert_before(node)

        node.replace_by(
            gate_stmts.U3(
                qubits=node.qubits,
                theta=theta_stmt.result,
                phi=phi_stmt.result,
                lam=lam_stmt.result,
            )
        )

        return rewrite_abc.RewriteResult(has_done_something=True)

    def rewrite_Rx(self, node: gate_stmts.Rx) -> rewrite_abc.RewriteResult:
        (phi_stmt := py.Constant(-0.25)).insert_before(node)
        (lam_stmt := py.Constant(0.25)).insert_before(node)

        node.replace_by(
            gate_stmts.U3(
                qubits=node.qubits,
                theta=node.angle,
                phi=phi_stmt.result,
                lam=lam_stmt.result,
            )
        )

        return rewrite_abc.RewriteResult(has_done_something=True)

    def rewrite_Ry(self, node: gate_stmts.Ry) -> rewrite_abc.RewriteResult:
        (phi_stmt := py.Constant(0.0)).insert_before(node)
        (lam_stmt := py.Constant(0.0)).insert_before(node)

        node.replace_by(
            gate_stmts.U3(
                qubits=node.qubits,
                theta=node.angle,
                phi=phi_stmt.result,
                lam=lam_stmt.result,
            )
        )

        return rewrite_abc.RewriteResult(has_done_something=True)

    def rewrite_Rz(self, node: gate_stmts.Rz) -> rewrite_abc.RewriteResult:
        (theta_stmt := py.Constant(0.0)).insert_before(node)
        (phi_stmt := py.Constant(0.0)).insert_before(node)

        node.replace_by(
            gate_stmts.U3(
                qubits=node.qubits,
                theta=theta_stmt.result,
                phi=phi_stmt.result,
                lam=node.angle,
            )
        )

        return rewrite_abc.RewriteResult(has_done_something=True)
