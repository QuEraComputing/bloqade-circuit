from kirin import ir
from kirin.rewrite import abc as rewrite_abc
from kirin.dialects import py


class InsertGetQubit(rewrite_abc.RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> rewrite_abc.RewriteResult:
        from bloqade.qasm2 import core

        if (
            not isinstance(node, core.QRegNew)
            or not isinstance(n_qubits_stmt := node.n_qubits.owner, py.Constant)
            or not isinstance(n_qubits := n_qubits_stmt.value.unwrap(), int)
            or (block := node.parent_block) is None
        ):
            return rewrite_abc.RewriteResult()

        n_qubits_stmt.detach()
        node.detach()
        if block.first_stmt is None:
            block.stmts.append(n_qubits_stmt)
            block.stmts.append(node)
        else:
            node.insert_before(block.first_stmt)
            n_qubits_stmt.insert_before(block.first_stmt)

        for idx_val in range(n_qubits):
            idx = py.constant.Constant(value=idx_val)
            qubit = core.QRegGet(node.result, idx=idx.result)
            qubit.insert_after(node)
            idx.insert_after(node)

        return rewrite_abc.RewriteResult(has_done_something=True)
