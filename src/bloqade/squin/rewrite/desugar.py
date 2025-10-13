from warnings import warn

from kirin import ir, types
from kirin.dialects import py, ilist
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

    NOTE: this pass can be removed once we decide to disallow the syntax apply(op: Op, qubits: list)
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        if not isinstance(node, ApplyAny):
            return RewriteResult()

        op = node.operator
        qubits = node.qubits

        if len(qubits) == 0:
            # NOTE: this is invalid syntax, but we don't error in rewrites
            return RewriteResult()

        if all(q.type.is_subseteq(QubitType) for q in qubits):
            # NOTE: this is the syntax we want; the entire rewrite becomes unnecessary
            # once we disallow the old syntax (just wrap Apply directly)
            apply_stmt = Apply(op, qubits)
            node.replace_by(apply_stmt)
            return RewriteResult(has_done_something=True)

        if len(qubits) > 1:
            # NOTE: multiple arguments, that aren't qubits, let's bail
            return RewriteResult()

        qubit_type = qubits[0].type
        is_qubit_list = qubit_type.is_subseteq(ilist.IListType[QubitType, types.Any])

        if not is_qubit_list:
            return RewriteResult()

        # NOTE: deprecated syntax: we have a single list of qubits here
        warn(
            "The syntax `apply(operator: Op, qubits: list[Qubit])` is deprecated and may already lead to errors. Use `apply(operator: Op, *qubits: Qubit)` instead."
        )
        if not isinstance(qubit_type.vars[1], types.Literal):
            # NOTE: unknown size, nothing we can do here, it will probably error down the road somewhere
            return RewriteResult()

        n = qubit_type.vars[1].data
        if not isinstance(n, int):
            # wat?
            return RewriteResult()

        qubits_rewrite = []
        for i in range(n):
            (idx := py.Constant(i)).insert_before(node)
            (get_item := py.GetItem(qubits[0], idx.result)).insert_before(node)
            qubits_rewrite.append(get_item.result)

        apply_stmt = Apply(op, tuple(qubits_rewrite))
        node.replace_by(apply_stmt)
        return RewriteResult(has_done_something=True)
