from kirin import ir
from kirin.dialects import py, func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.qasm2.dialects.core import stmts as core_stmts

CORE_TO_SQUIN_MAP = {
    core_stmts.QRegNew: squin.qubit.qalloc,
    core_stmts.Reset: squin.qubit.reset,
}


class QASM2CoreToSquin(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        if isinstance(node, core_stmts.QRegGet):
            py_get_item = py.GetItem(
                obj=node.reg,
                index=node.idx,
            )
            node.replace_by(py_get_item)
            return RewriteResult(has_done_something=True)

        if isinstance(node, core_stmts.QRegNew):
            args = (node.n_qubits,)
        elif isinstance(node, core_stmts.Reset):
            args = (node.qarg,)
        else:
            return RewriteResult()

        new_stmt = func.Invoke(
            callee=CORE_TO_SQUIN_MAP[type(node)],
            inputs=args,
        )
        node.replace_by(new_stmt)
        return RewriteResult(has_done_something=True)
