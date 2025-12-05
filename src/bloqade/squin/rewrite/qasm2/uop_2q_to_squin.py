from kirin import ir
from kirin.dialects import func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.qasm2.dialects.uop import stmts as uop_stmts

CONTROLLED_GATES_TO_SQUIN_MAP = {
    uop_stmts.CX: squin.cx,
    uop_stmts.CZ: squin.cz,
    uop_stmts.CY: squin.cy,
}


class QASM2UOp2QToSquin(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        squin_controlled_gate = CONTROLLED_GATES_TO_SQUIN_MAP.get(type(node))
        if squin_controlled_gate is None:
            return RewriteResult()

        invoke_stmt = func.Invoke(
            callee=squin_controlled_gate,
            inputs=(node.ctrl, node.qarg),
        )
        node.replace_by(invoke_stmt)
        return RewriteResult(has_done_something=True)
