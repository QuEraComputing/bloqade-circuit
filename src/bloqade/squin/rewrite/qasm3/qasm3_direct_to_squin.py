from kirin import ir
from kirin.dialects import func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.qasm3.dialects.uop import stmts as uop_stmts
from bloqade.qasm3.dialects.core import stmts as core_stmts

QASM3_TO_SQUIN_MAP = {
    core_stmts.QRegNew: squin.qubit.qalloc,
    core_stmts.Reset: squin.qubit.reset,
    uop_stmts.X: squin.x,
    uop_stmts.Y: squin.y,
    uop_stmts.Z: squin.z,
    uop_stmts.H: squin.h,
    uop_stmts.S: squin.s,
    uop_stmts.T: squin.t,
    uop_stmts.CX: squin.cx,
    uop_stmts.CY: squin.cy,
    uop_stmts.CZ: squin.cz,
}


class QASM3DirectToSquin(RewriteRule):
    """
    Rewrite QASM3 statements that have a direct 1:1 mapping to their Squin equivalents.
    These statements do not require argument reordering or modification.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if type(node) not in QASM3_TO_SQUIN_MAP:
            return RewriteResult()

        squin_callee = QASM3_TO_SQUIN_MAP[type(node)]
        invoke_stmt = func.Invoke(
            callee=squin_callee,
            inputs=node.args,
        )
        node.replace_by(invoke_stmt)
        return RewriteResult(has_done_something=True)
