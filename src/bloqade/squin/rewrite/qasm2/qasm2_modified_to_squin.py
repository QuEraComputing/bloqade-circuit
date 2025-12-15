from math import pi

from kirin import ir
from kirin.dialects import py, func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.qasm2.dialects import glob, parallel
from bloqade.qasm2.dialects.uop import stmts as uop_stmts
from bloqade.qasm2.dialects.core import QRegGet

QASM2_TO_SQUIN_MAP = {
    parallel.RZ: squin.broadcast.rz,
    uop_stmts.RX: squin.rx,
    uop_stmts.RY: squin.ry,
    uop_stmts.RZ: squin.rz,
    uop_stmts.U1: squin.u3,
    uop_stmts.U2: squin.u3,
    uop_stmts.UGate: squin.u3,
    parallel.UGate: squin.broadcast.u3,
    glob.UGate: squin.broadcast.u3,
    # this doesn't need to be here because it goes against
    # the invoke usage convention seen below but
    QRegGet: py.GetItem,
}


class QASM2ModifiedToSquin(RewriteRule):
    """
    Rewrite all QASM2 statements to their Squin equivalents. Unlike QASM2DirectToSquin,
    these statements require their arguments to be modified/permuted to match the Squin equivalent.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        if type(node) not in QASM2_TO_SQUIN_MAP:
            return RewriteResult()

        if isinstance(node, QRegGet):
            py_get_item_stmt = py.GetItem(
                obj=node.reg,
                index=node.idx,
            )
            node.replace_by(py_get_item_stmt)
            return RewriteResult(has_done_something=True)

        squin_callee = QASM2_TO_SQUIN_MAP[type(node)]

        if isinstance(node, (uop_stmts.RX, uop_stmts.RY, uop_stmts.RZ)):
            # flip order
            new_args = (node.theta, node.qarg)
        elif isinstance(node, (parallel.RZ,)):
            # flip order
            new_args = (node.theta, node.qargs)
        elif isinstance(node, (uop_stmts.U1,)):
            zero_stmt = py.Constant(value=0.0)
            zero_stmt.insert_before(node)
            new_args = (zero_stmt.result, zero_stmt.result, node.lam, node.qarg)
        elif isinstance(node, uop_stmts.U2):
            pi_over_2_stmt = py.Constant(value=pi / 2)
            pi_over_2_stmt.insert_before(node)
            new_args = (pi_over_2_stmt.result, node.phi, node.lam, node.qarg)
        elif isinstance(node, (uop_stmts.UGate, parallel.UGate, glob.UGate)):
            new_args = (
                node.theta,
                node.phi,
                node.lam,
                (
                    node.qarg
                    if hasattr(node, "qarg")
                    else (node.registers if hasattr(node, "registers") else node.qargs)
                ),
            )
        else:
            return RewriteResult()

        invoke_stmt = func.Invoke(
            callee=squin_callee,
            inputs=new_args,
        )
        node.replace_by(invoke_stmt)

        return RewriteResult(has_done_something=True)
