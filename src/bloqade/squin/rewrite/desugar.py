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

    NOTE: this pass can be removed once we are at kirin v0.18 and we decide to
    disallow the syntax apply(op: Op, qubits: list)
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        if not isinstance(node, ApplyAny):
            return RewriteResult()

        op = node.operator
        qubits = node.qubits

        if all(q.type.is_subseteq(QubitType) for q in qubits):
            apply_stmt = Apply(op, qubits)
            node.replace_by(apply_stmt)
            return RewriteResult(has_done_something=True)

        if len(qubits) == 1 and (qubit_type := qubits[0].type).is_subseteq(
            ilist.IListType[QubitType, types.Any]
        ):
            warn(
                "The syntax `apply(operator: Op, qubits: list[Qubit])` is deprecated. Use `apply(operator: Op, *qubits: Qubit)` instead."
            )
            # NOTE: deprecated syntax
            # TODO: remove one we disallow apply(op: Op, q: ilist.IList[Qubit])
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

        if len(qubits) == 1:
            # NOTE: we might have a single ilist with wrong typing here
            # TODO: remove this elif clause once we're at kirin v0.18
            # NOTE: this is a temporary workaround for kirin#408
            # currently type inference fails here in for loops since the loop var
            # is an IList for some reason

            if not isinstance(qubits[0], ir.ResultValue):
                return RewriteResult()

            is_ilist = isinstance(qbit_stmt := qubits[0].stmt, ilist.New)

            if is_ilist:

                qbit_getindices = qbit_stmt.values

                if not all(
                    isinstance(qbit_getindex_result, ir.ResultValue)
                    for qbit_getindex_result in qbit_getindices
                ):
                    return RewriteResult()

            else:
                qbit_getindices = qubits

            stmt = Apply(operator=op, qubits=tuple(qbit_getindices))
            node.replace_by(stmt)
            return RewriteResult(has_done_something=True)

        return RewriteResult()
