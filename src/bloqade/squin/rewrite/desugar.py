from kirin import ir, types
from kirin.dialects import ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin.qubit import (
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
