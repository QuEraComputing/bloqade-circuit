from math import pi

from kirin import ir
from kirin.dialects import py, func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.qasm2.dialects.uop import stmts as uop_stmts

PARAMETRIZED_1Q_GATES_TO_SQUIN_MAP = {
    uop_stmts.UGate: squin.u3,
    uop_stmts.U1: squin.u3,
    uop_stmts.U2: squin.u3,
    uop_stmts.RZ: squin.rz,
    uop_stmts.RX: squin.rx,
    uop_stmts.RY: squin.ry,
}


class QASM2ParametrizedUOp1QToSquin(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        if isinstance(node, (uop_stmts.RX, uop_stmts.RY, uop_stmts.RZ)):
            args = (node.theta, node.qarg)
        elif isinstance(node, (uop_stmts.UGate)):
            args = (node.theta, node.phi, node.lam, node.qarg)
        elif isinstance(node, (uop_stmts.U1)):
            zero_stmt = py.Constant(value=0.0)
            zero_stmt.insert_before(node)
            args = (zero_stmt.result, zero_stmt.result, node.lam, node.qarg)
        elif isinstance(node, (uop_stmts.U2)):
            half_pi_stmt = py.Constant(value=pi / 2)
            half_pi_stmt.insert_before(node)
            args = (half_pi_stmt.result, node.phi, node.lam, node.qarg)
        else:
            return RewriteResult()

        squin_equivalent_stmt = PARAMETRIZED_1Q_GATES_TO_SQUIN_MAP[type(node)]
        invoke_stmt = func.Invoke(
            callee=squin_equivalent_stmt,
            inputs=args,
        )
        node.replace_by(invoke_stmt)

        return RewriteResult(has_done_something=True)
