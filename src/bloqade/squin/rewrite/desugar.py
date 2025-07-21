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
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        if not isinstance(node, ApplyAny):
            return RewriteResult()

        op = node.operator
        qubits = node.qubits

        if len(qubits) > 1 and all(q.type.is_subseteq(QubitType) for q in qubits):
            (qubits_ilist_stmt := ilist.New(qubits)).insert_before(
                node
            )  # qubits is just a tuple of SSAValues
            qubits_ilist = qubits_ilist_stmt.result

        elif len(qubits) == 1 and qubits[0].type.is_subseteq(QubitType):
            (qubits_ilist_stmt := ilist.New(qubits)).insert_before(node)
            qubits_ilist = qubits_ilist_stmt.result

        elif len(qubits) == 1 and qubits[0].type.is_subseteq(
            ilist.IListType[QubitType, types.Any]
        ):
            qubits_ilist = qubits[0]

        elif len(qubits) == 1:
            # TODO: remove this elif clause once we're at kirin v0.18
            # NOTE: this is a temporary workaround for kirin#408
            # currently type inference fails here in for loops since the loop var
            # is an IList for some reason

            if not isinstance(qubits[0], ir.ResultValue):
                return RewriteResult()

            is_ilist = isinstance(qbit_stmt := qubits[0].stmt, ilist.New)

            if is_ilist:

                if not all(
                    isinstance(qbit_getindex_result, ir.ResultValue)
                    for qbit_getindex_result in qbit_stmt.values
                ):
                    return RewriteResult()

                # Get the parent statement that the qubit came from
                # (should be a GetItem instance, see logic below)
                qbit_getindices = [
                    qbit_getindex_result.stmt
                    for qbit_getindex_result in qbit_stmt.values
                ]
            else:
                qbit_getindices = [qubit.stmt for qubit in qubits]

            if any(
                not isinstance(qbit_getindex, py.indexing.GetItem)
                for qbit_getindex in qbit_getindices
            ):
                return RewriteResult()

            # The GetItem should have been applied on something that returns an IList of Qubits
            if any(
                not qbit_getindex.obj.type.is_subseteq(
                    ilist.IListType[QubitType, types.Any]
                )
                for qbit_getindex in qbit_getindices
            ):
                return RewriteResult()

            if is_ilist:
                qubits_ilist = qbit_stmt.result
            else:
                (qubits_ilist_stmt := ilist.New(values=[qubits[0]])).insert_before(node)
                qubits_ilist = qubits_ilist_stmt.result
        else:
            return RewriteResult()

        stmt = Apply(operator=op, qubits=qubits_ilist)
        node.replace_by(stmt)
        return RewriteResult(has_done_something=True)
