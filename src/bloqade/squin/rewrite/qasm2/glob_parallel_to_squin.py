from kirin import ir
from kirin.dialects import func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.qasm2.dialects import glob, parallel


class QASM2GlobParallelToSquin(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case glob.UGate() | parallel.UGate() | parallel.RZ():
                return self.rewrite_1q_gates(node)
            case _:
                return RewriteResult()

        return RewriteResult(has_done_something=True)

    def rewrite_1q_gates(
        self, stmt: glob.UGate | parallel.UGate | parallel.RZ
    ) -> RewriteResult:

        match stmt:
            case glob.UGate(theta=theta, phi=phi, lam=lam) | parallel.UGate(
                theta=theta, phi=phi, lam=lam
            ):
                # ever so slight naming difference,
                # exists because intended semantics are different
                match stmt:
                    case glob.UGate():
                        qargs = stmt.registers
                    case parallel.UGate():
                        qargs = stmt.qargs

                invoke_u_broadcast_stmt = func.Invoke(
                    callee=squin.broadcast.u3,
                    inputs=(theta, phi, lam, qargs),
                )
                stmt.replace_by(invoke_u_broadcast_stmt)
            case parallel.RZ(theta=theta, qargs=qargs):
                invoke_rz_broadcast_stmt = func.Invoke(
                    callee=squin.broadcast.rz,
                    inputs=(theta, qargs),
                )
                stmt.replace_by(invoke_rz_broadcast_stmt)
            case _:
                return RewriteResult()

        return RewriteResult(has_done_something=True)
