from kirin import ir
from kirin.dialects import py, func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.qasm2.dialects.core import stmts as core_stmts


class QASM2CoreToSquin(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case core_stmts.QRegNew(n_qubits=n_qubits):
                qalloc_invoke_stmt = func.Invoke(
                    callee=squin.qubit.qalloc, inputs=(n_qubits,)
                )
                node.replace_by(qalloc_invoke_stmt)
            case core_stmts.Reset(qarg=qarg):
                reset_invoke_stmt = func.Invoke(
                    callee=squin.qubit.reset, inputs=(qarg,)
                )
                node.replace_by(reset_invoke_stmt)
            case core_stmts.QRegGet(reg=reg, idx=idx):
                get_item_stmt = py.GetItem(
                    obj=reg,
                    index=idx,
                )
                node.replace_by(get_item_stmt)
            case _:
                return RewriteResult()

        return RewriteResult(has_done_something=True)
