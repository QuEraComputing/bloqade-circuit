from kirin import ir
from kirin.dialects import func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.qasm2.dialects.uop import stmts as uop_stmts

ONE_Q_GATES_TO_SQUIN_MAP = {
    uop_stmts.X: squin.x,
    uop_stmts.Y: squin.y,
    uop_stmts.Z: squin.z,
    uop_stmts.H: squin.h,
    uop_stmts.S: squin.s,
    uop_stmts.Sdag: squin.s_adj,
    uop_stmts.SX: squin.sqrt_x,
    uop_stmts.SXdag: squin.sqrt_x_adj,
    uop_stmts.Tdag: squin.t_adj,
    uop_stmts.T: squin.t,
}


class QASM2UOp1QToSquin(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        squin_1q_gate = ONE_Q_GATES_TO_SQUIN_MAP.get(type(node))
        if squin_1q_gate is None:
            return RewriteResult()

        invoke_stmt = func.Invoke(
            callee=squin_1q_gate,
            inputs=(node.qarg,),
        )
        node.replace_by(invoke_stmt)

        return RewriteResult(has_done_something=True)
