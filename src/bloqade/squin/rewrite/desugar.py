from kirin import ir, types
from kirin.dialects import ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin.qubit import (
    Apply,
    ApplyAny,
    QubitType,
    MeasureAny,
    MeasureQubit,
    MeasureQubitList,
)


class MeasureDesugarRule(RewriteRule):
    """
    Desugar measure operations in the circuit.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        if not isinstance(node, MeasureAny):
            return RewriteResult()

        if node.input.type.is_subseteq(QubitType):
            node.replace_by(
                MeasureQubit(
                    qubit=node.input,
                )
            )
            return RewriteResult(has_done_something=True)
        elif node.input.type.is_subseteq(ilist.IListType[QubitType, types.Any]):
            node.replace_by(
                MeasureQubitList(
                    qubits=node.input,
                )
            )
            return RewriteResult(has_done_something=True)

        return RewriteResult()


class ApplyDesugarRule(RewriteRule):
    """
    Desugar apply operators in the kernel.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        if not isinstance(node, ApplyAny):
            return RewriteResult()

        op = node.operator
        qubits = node.qubits

        qubits_ilist = None
        if len(qubits) > 1 and all(q.type.is_subseteq(QubitType) for q in qubits):
            (qubits_ilist_stmt := ilist.New(qubits)).insert_before(node)
            qubits_ilist = qubits_ilist_stmt.result

        elif len(qubits) == 1 and qubits[0].type.is_subseteq(QubitType):
            (qubits_ilist_stmt := ilist.New(qubits)).insert_before(node)
            qubits_ilist = qubits_ilist_stmt.result

        elif len(qubits) == 1 and qubits[0].type.is_subseteq(
            ilist.IListType[QubitType, types.Any]
        ):
            qubits_ilist = qubits[0]

        if qubits_ilist is None:
            return RewriteResult()

        stmt = Apply(operator=op, qubits=qubits_ilist)
        node.replace_by(stmt)
        return RewriteResult(has_done_something=True)
