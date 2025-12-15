from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.qasm2.dialects.core import stmts as core_stmts


class QASM2QRegGetToSquin(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        if not isinstance(node, core_stmts.QRegGet):
            return RewriteResult()

        py_get_item = py.GetItem(
            obj=node.reg,
            index=node.idx,
        )
        node.replace_by(py_get_item)
        return RewriteResult(has_done_something=True)
