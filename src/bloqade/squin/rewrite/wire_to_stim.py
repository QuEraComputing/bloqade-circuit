from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import stim
from bloqade.squin import op, wire
from bloqade.squin.rewrite.wrap_analysis import AddressAttribute
from bloqade.squin.rewrite.stim_rewrite_util import (
    rewrite_Control,
    get_stim_1q_gate,
    are_sites_compatible,
    insert_qubit_idx_from_address,
    insert_qubit_idx_from_wire_ssa,
)


class SquinWireToStim(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case wire.Apply() | wire.Broadcast():
                are_sites_compatible(node)
                return self.rewrite_Apply_and_Broadcast(node)
            case wire.Wrap():
                return self.rewrite_Wrap(node)
            case wire.Measure():
                return self.rewrite_Measure(node)
            case wire.Reset():
                return self.rewrite_Reset(node)
            case wire.MeasureAndReset():
                return self.rewrite_MeasureAndReset(node)
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

        stim_1q_op = get_stim_1q_gate(applied_op)
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

    def rewrite_Wrap(self, wrap_stmt: wire.Wrap) -> RewriteResult:

        wire_origin_stmt = wrap_stmt.wire.owner
        if isinstance(wire_origin_stmt, wire.Unwrap):
            wire_origin_stmt.delete()
            wrap_stmt.delete()
            return RewriteResult(has_done_something=True)

        return RewriteResult()

    def rewrite_Measure(self, measure_stmt: wire.Measure) -> RewriteResult:

        wire_ssa = measure_stmt.wire
        address_attr = wire_ssa.hints.get("address")
        if address_attr is None:
            return RewriteResult()
        assert isinstance(address_attr, AddressAttribute)

        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=address_attr, stmt_to_insert_before=measure_stmt
        )

        if qubit_idx_ssas is None:
            return RewriteResult()

        prob_noise_stmt = py.constant.Constant(0.0)
        stim_measure_stmt = stim.collapse.MZ(
            p=prob_noise_stmt.result,
            targets=qubit_idx_ssas,
        )
        prob_noise_stmt.insert_before(measure_stmt)
        stim_measure_stmt.insert_before(measure_stmt)

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

    def rewrite_MeasureAndReset(self, meas_and_reset_stmt: wire.MeasureAndReset):

        address_attr = meas_and_reset_stmt.wire.hints.get("address")
        if address_attr is None:
            return RewriteResult()
        assert isinstance(address_attr, AddressAttribute)
        qubit_idx_ssas = insert_qubit_idx_from_address(
            address_attr, stmt_to_insert_before=meas_and_reset_stmt
        )
        if qubit_idx_ssas is None:
            return RewriteResult()

        error_p_stmt = py.Constant(0.0)
        stim_mz_stmt = stim.collapse.MZ(targets=qubit_idx_ssas, p=error_p_stmt.result)
        stim_rz_stmt = stim.collapse.RZ(
            targets=qubit_idx_ssas,
        )
        error_p_stmt.insert_before(meas_and_reset_stmt)
        stim_mz_stmt.insert_before(meas_and_reset_stmt)
        stim_rz_stmt.insert_before(meas_and_reset_stmt)

        return RewriteResult(has_done_something=True)
