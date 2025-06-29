from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin import op, wire, noise
from bloqade.stim.rewrite.util import (
    SQUIN_STIM_OP_MAPPING,
    rewrite_Control,
    rewrite_QubitLoss,
    insert_qubit_idx_from_wire_ssa,
)


class SquinWireToStim(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        match node:
            case wire.Apply() | wire.Broadcast():
                return self.rewrite_Apply_and_Broadcast(node)
            case _:
                return RewriteResult()

    def rewrite_Apply_and_Broadcast(
        self, stmt: wire.Apply | wire.Broadcast
    ) -> RewriteResult:

        # this is an SSAValue, need it to be the actual operator
        applied_op = stmt.operator.owner

        if isinstance(applied_op, noise.stmts.QubitLoss):
            return rewrite_QubitLoss(stmt)

        assert isinstance(applied_op, op.stmts.Operator)

        if isinstance(applied_op, op.stmts.Control):
            return rewrite_Control(stmt)

        stim_1q_op = SQUIN_STIM_OP_MAPPING.get(type(applied_op))
        if stim_1q_op is None:
            return RewriteResult()

        qubit_idx_ssas = insert_qubit_idx_from_wire_ssa(
            wire_ssas=stmt.inputs, stmt_to_insert_before=stmt
        )
        if qubit_idx_ssas is None:
            return RewriteResult()

        stim_1q_stmt = stim_1q_op(targets=tuple(qubit_idx_ssas))

        # Get the wires from the inputs of Apply or Broadcast,
        # then put those as the result of the current stmt
        # before replacing it entirely
        for input_wire, output_wire in zip(stmt.inputs, stmt.results):
            output_wire.replace_by(input_wire)

        stmt.replace_by(stim_1q_stmt)

        return RewriteResult(has_done_something=True)
