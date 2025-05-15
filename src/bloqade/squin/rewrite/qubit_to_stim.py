from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import stim
from bloqade.squin import op, qubit
from bloqade.squin.rewrite.wrap_analysis import AddressAttribute
from bloqade.squin.rewrite.stim_rewrite_util import (
    rewrite_Control,
    get_stim_1q_gate,
    are_sites_compatible,
    insert_qubit_idx_from_address,
)


class SquinQubitToStim(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        rewrite_methods = {
            qubit.Apply: self.rewrite_Apply_and_Broadcast,
            qubit.Broadcast: self.rewrite_Apply_and_Broadcast,
            qubit.MeasureQubit: self.rewrite_Measure,
            qubit.MeasureQubitList: self.rewrite_Measure,
            qubit.Reset: self.rewrite_Reset,
            qubit.MeasureAndReset: self.rewrite_MeasureAndReset,
        }

        rewrite_method = rewrite_methods.get(type(node))
        if rewrite_method is None:
            return RewriteResult()

        return rewrite_method(node)

    # handle Control
    def rewrite_Apply_and_Broadcast(
        self, stmt: qubit.Apply | qubit.Broadcast
    ) -> RewriteResult:
        """
        Rewrite Apply and Broadcast nodes to their stim equivalent statements.
        """
        if not are_sites_compatible(stmt):
            return RewriteResult()

        # this is an SSAValue, need it to be the actual operator
        applied_op = stmt.operator.owner
        assert isinstance(applied_op, op.stmts.Operator)

        if isinstance(applied_op, op.stmts.Control):
            return rewrite_Control(stmt)

        # need to handle Control through separate means
        # but we can handle X, Y, Z, H, and S here just fine
        stim_1q_op = get_stim_1q_gate(applied_op)
        if stim_1q_op is None:
            return RewriteResult()

        address_attr = stmt.qubits.hints.get("address")
        if address_attr is None:
            return RewriteResult()

        assert isinstance(address_attr, AddressAttribute)
        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=address_attr, stmt_to_insert_before=stmt
        )

        if qubit_idx_ssas is None:
            return RewriteResult()

        stim_1q_stmt = stim_1q_op(targets=tuple(qubit_idx_ssas))
        stmt.replace_by(stim_1q_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_Measure(
        self, measure_stmt: qubit.MeasureQubit | qubit.MeasureQubitList
    ) -> RewriteResult:

        # qubit_ssa will always be an ilist of qubits
        # but need to be careful with singular vs plural "qubit" attribute name
        if isinstance(measure_stmt, qubit.MeasureQubit):
            qubit_ssa = measure_stmt.qubit
        elif isinstance(measure_stmt, qubit.MeasureQubitList):
            qubit_ssa = measure_stmt.qubits
        else:
            return RewriteResult()

        address_attr = qubit_ssa.hints.get("address")
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

    def rewrite_Reset(self, reset_stmt: qubit.Reset) -> RewriteResult:
        qubit_ilist_ssa = reset_stmt.qubits
        # qubits are in an ilist which makes up an AddressTuple
        address_attr = qubit_ilist_ssa.hints.get("address")
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

    def rewrite_MeasureAndReset(
        self, meas_and_reset_stmt: qubit.MeasureAndReset
    ) -> RewriteResult:

        address_attr = meas_and_reset_stmt.qubits.hints.get("address")
        if address_attr is None:
            return RewriteResult()

        assert isinstance(address_attr, AddressAttribute)
        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=address_attr, stmt_to_insert_before=meas_and_reset_stmt
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
