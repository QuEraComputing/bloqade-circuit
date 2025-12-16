from math import pi

from kirin import ir
from kirin.dialects import py, func, ilist
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
    # These two entries don't need to be here, but are included for completeness
    glob.UGate: squin.broadcast.u3,
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

        if isinstance(node, (uop_stmts.RX, uop_stmts.RY, uop_stmts.RZ, parallel.RZ)):
            new_args = (
                node.theta,
                node.qargs if isinstance(node, parallel.RZ) else node.qarg,
            )
        elif isinstance(node, (uop_stmts.U1,)):
            zero_stmt = py.Constant(value=0.0)
            zero_stmt.insert_before(node)
            new_args = (zero_stmt.result, zero_stmt.result, node.lam, node.qarg)
        elif isinstance(node, uop_stmts.U2):
            pi_over_2_stmt = py.Constant(value=pi / 2)
            pi_over_2_stmt.insert_before(node)
            new_args = (pi_over_2_stmt.result, node.phi, node.lam, node.qarg)
        elif isinstance(node, (uop_stmts.UGate, parallel.UGate, glob.UGate)):
            angle_args = (node.theta, node.phi, node.lam)
            if isinstance(node, uop_stmts.UGate):
                qubit_args = node.qarg
            elif isinstance(node, glob.UGate):
                return self.rewrite_glob_UGate(node)
            else:
                qubit_args = node.qargs
            new_args = angle_args + (qubit_args,)
        else:
            return RewriteResult()

        invoke_stmt = func.Invoke(
            callee=squin_callee,
            inputs=new_args,
        )
        node.replace_by(invoke_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_glob_UGate(self, node: glob.UGate) -> RewriteResult:

        # assume that QASM2DirectToSquin has already run, which converts QRegNew to qubit.new in the squin dialect.
        # Then you're left with an ilist of ilists of qubit.news, for which a new squin.broadcast.u3 should be created.

        ilist_of_registers = node.registers.owner
        assert isinstance(ilist_of_registers, ilist.New)

        for register_ilist in ilist_of_registers.values:
            invoke_stmt = func.Invoke(
                callee=squin.broadcast.u3,
                inputs=(node.theta, node.phi, node.lam, register_ilist),
            )
            invoke_stmt.insert_before(node)

        node.delete()
        return RewriteResult(has_done_something=True)
