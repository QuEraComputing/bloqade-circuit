from kirin import ir
from kirin.dialects import py, func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.qasm3.dialects.uop import stmts as uop_stmts
from bloqade.qasm3.dialects.core import QRegGet

QASM3_TO_SQUIN_MAP = {
    uop_stmts.RX: squin.rx,
    uop_stmts.RY: squin.ry,
    uop_stmts.RZ: squin.rz,
    uop_stmts.UGate: squin.u3,
    QRegGet: py.GetItem,
}


class QASM3ModifiedToSquin(RewriteRule):
    """
    Rewrite QASM3 statements to their Squin equivalents where arguments
    need to be reordered or modified to match the Squin calling convention.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if type(node) not in QASM3_TO_SQUIN_MAP:
            return RewriteResult()

        if isinstance(node, QRegGet):
            py_get_item_stmt = py.GetItem(
                obj=node.reg,
                index=node.idx,
            )
            node.replace_by(py_get_item_stmt)
            return RewriteResult(has_done_something=True)

        squin_callee = QASM3_TO_SQUIN_MAP[type(node)]

        if isinstance(node, (uop_stmts.RX, uop_stmts.RY, uop_stmts.RZ)):
            # Squin expects (angle, qubit), QASM3 RotationGate has (qarg, theta)
            new_args = (node.theta, node.qarg)
        elif isinstance(node, uop_stmts.UGate):
            # Squin expects (theta, phi, lam, qubit), QASM3 UGate has (qarg, theta, phi, lam)
            new_args = (node.theta, node.phi, node.lam, node.qarg)
        else:
            return RewriteResult()

        invoke_stmt = func.Invoke(
            callee=squin_callee,
            inputs=new_args,
        )
        node.replace_by(invoke_stmt)
        return RewriteResult(has_done_something=True)
