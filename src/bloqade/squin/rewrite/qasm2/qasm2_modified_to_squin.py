from math import pi

from kirin import ir
from kirin.dialects import py, func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.qasm2.dialects import glob, parallel
from bloqade.qasm2.dialects.uop import stmts as uop_stmts

QASM2_TO_SQUIN_MAP = {
    # flipped argument order
    parallel.RZ: squin.broadcast.rz,
    # flipped argument order
    uop_stmts.RX: squin.rx,
    uop_stmts.RY: squin.ry,
    uop_stmts.RZ: squin.rz,
    # need to inject default values for parameters
    uop_stmts.U1: squin.u3,
    uop_stmts.U2: squin.u3,
    # UGATE: qarg, theta, phi, lam
    # squin.u3: theta, phi, lam, qubit
    uop_stmts.UGate: squin.u3,
    # parallel.UGate: qargs, theta, phi, lam
    # broadcast.u3: theta, phi, lam, qubits
    parallel.UGate: squin.broadcast.u3,
    # glob.UGate: registers, theta, phi, lam
    glob.UGate: squin.broadcast.u3,
}


class QASM2ModifiedToSquin(RewriteRule):
    """
    Rewrite all QASM2 statements to their Squin equivalents using invoke.
    Specifically, there is a 1:1 mapping from the QASM2 statement arguments to the squin invoke inputs.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        if type(node) not in QASM2_TO_SQUIN_MAP:
            return RewriteResult()

        squin_callee = QASM2_TO_SQUIN_MAP[type(node)]

        if isinstance(node, (uop_stmts.RX, uop_stmts.RY, uop_stmts.RZ)):
            print(node.args)
            # flip argument order
            print(node.qarg)
            invoke_stmt = func.Invoke(
                callee=squin_callee,
                inputs=(node.theta, node.qarg),
            )
        elif isinstance(node, (parallel.RZ,)):
            # flip argument order, note "qargs" vs "qarg" above
            invoke_stmt = func.Invoke(
                callee=squin_callee,
                inputs=(node.theta, node.qargs),
            )
        elif isinstance(node, (uop_stmts.U1,)):
            zero_stmt = py.Constant(value=0.0)
            zero_stmt.insert_before(node)
            invoke_stmt = func.Invoke(
                callee=squin_callee,
                inputs=(zero_stmt.result, zero_stmt.result, node.lam, node.qarg),
            )
        elif isinstance(node, uop_stmts.U2):
            pi_over_2_stmt = py.Constant(value=pi / 2)
            pi_over_2_stmt.insert_before(node)
            invoke_stmt = func.Invoke(
                callee=squin_callee,
                inputs=(pi_over_2_stmt.result, node.phi, node.lam, node.qarg),
            )
        elif isinstance(node, (uop_stmts.UGate, parallel.UGate, glob.UGate)):
            invoke_stmt = func.Invoke(
                callee=squin_callee,
                inputs=(
                    node.theta,
                    node.phi,
                    node.lam,
                    (
                        node.qarg
                        if hasattr(node, "qarg")
                        else (
                            node.registers if hasattr(node, "registers") else node.qargs
                        )
                    ),
                ),
            )
        else:
            return RewriteResult()

        node.replace_by(invoke_stmt)

        return RewriteResult(has_done_something=True)
