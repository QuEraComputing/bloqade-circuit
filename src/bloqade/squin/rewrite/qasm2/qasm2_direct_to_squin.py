from kirin import ir
from kirin.dialects import func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.qasm2.dialects.uop import stmts as uop_stmts
from bloqade.qasm2.dialects.core import stmts as core_stmts

QASM2_TO_SQUIN_MAP = {
    core_stmts.QRegNew: squin.qubit.qalloc,
    core_stmts.Reset: squin.qubit.reset,
    uop_stmts.X: squin.x,
    uop_stmts.Y: squin.y,
    uop_stmts.Z: squin.z,
    uop_stmts.H: squin.h,
    uop_stmts.S: squin.s,
    uop_stmts.T: squin.t,
    uop_stmts.SX: squin.sqrt_x,
    uop_stmts.Tdag: squin.t_adj,
    uop_stmts.Sdag: squin.s_adj,
    uop_stmts.SXdag: squin.sqrt_x_adj,
    uop_stmts.CX: squin.cx,
    uop_stmts.CZ: squin.cz,
    uop_stmts.CY: squin.cy,
    core_stmts.QRegNew: squin.qubit.qalloc,
    core_stmts.Reset: squin.qubit.reset,
}


class QASM2DirectToSquin(RewriteRule):
    """
    Rewrites all QASM2 statements that do not require their arguments be modified/permuted to their Squin equivalent.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        if type(node) not in QASM2_TO_SQUIN_MAP:
            return RewriteResult()

        squin_callee = QASM2_TO_SQUIN_MAP[type(node)]
        invoke_stmt = func.Invoke(
            callee=squin_callee,
            inputs=node.args,
        )
        node.replace_by(invoke_stmt)
        return RewriteResult(has_done_something=True)
