"""Rewrite rules applied before QASM3 emission."""

from kirin import ir
from kirin.dialects import func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.qasm3.dialects.core.stmts import QRegNew


class SquinQallocToQRegNew(RewriteRule):
    """Replace func.Invoke(qalloc, size) with QRegNew(size).

    When emitting SQUIN IR to QASM3, qubit allocation is represented as a
    func.Invoke to the squin.qubit.qalloc kernel.  This rule lowers that
    back to the native qasm3.core.QRegNew statement so the normal emit path
    in core/_emit.py handles it cleanly.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, func.Invoke):
            return RewriteResult()
        if node.callee.sym_name != "qalloc":
            return RewriteResult()
        if len(node.args) != 1:
            return RewriteResult()

        qreg_new = QRegNew(n_qubits=node.args[0])
        node.replace_by(qreg_new)
        return RewriteResult(has_done_something=True)
