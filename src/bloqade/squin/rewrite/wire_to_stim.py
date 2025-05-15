from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import stim
from bloqade.squin import op, wire
from bloqade.squin.rewrite.wrap_analysis import AddressAttribute
from bloqade.squin.rewrite.stim_rewrite_util import (
    SQUIN_STIM_GATE_MAPPING,
    rewrite_Control,
    are_sites_compatible,
    insert_qubit_idx_from_address,
    insert_qubit_idx_from_wire_ssa,
)


class SquinWireToStim(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        match node:
            case wire.Apply() | wire.Broadcast():
                return self.rewrite_Apply_and_Broadcast(node)
            case wire.Reset():
                return self.rewrite_Reset(node)
            case _:
                return RewriteResult()

    def rewrite_Apply_and_Broadcast(
        self, stmt: wire.Apply | wire.Broadcast
    ) -> RewriteResult:

        if not are_sites_compatible(stmt):
            return RewriteResult()

        # this is an SSAValue, need it to be the actual operator
        applied_op = stmt.operator.owner
        assert isinstance(applied_op, op.stmts.Operator)

        if isinstance(applied_op, op.stmts.Control):
            return rewrite_Control(stmt)

        stim_1q_op = SQUIN_STIM_GATE_MAPPING.get(type(applied_op))
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

    def rewrite_Reset(self, reset_stmt: wire.Reset) -> RewriteResult:
        address_attr = reset_stmt.wire.hints.get("address")
        if address_attr is None:
            return RewriteResult()
        assert isinstance(address_attr, AddressAttribute)
        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=address_attr, stmt_to_insert_before=reset_stmt
        )
        if qubit_idx_ssas is None:
            return RewriteResult()

        stim_rz_stmt = stim.collapse.stmts.RZ(targets=qubit_idx_ssas)
        reset_stmt.replace_by(stim_rz_stmt)

        return RewriteResult(has_done_something=True)
