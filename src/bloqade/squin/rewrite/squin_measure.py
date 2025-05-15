# create rewrite rule name SquinMeasureToStim using kirin
from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import stim
from bloqade.squin import wire, qubit
from bloqade.squin.rewrite.wrap_analysis import AddressAttribute
from bloqade.squin.rewrite.stim_rewrite_util import (
    is_measure_result_used,
    insert_qubit_idx_from_address,
)


class SquinMeasureToStim(RewriteRule):
    """
    Rewrite squin measure-related statements to stim statements.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case qubit.MeasureQubit() | qubit.MeasureQubitList() | wire.Measure():
                return self.rewrite_Measure(node)
            case qubit.MeasureAndReset() | wire.MeasureAndReset():
                return self.rewrite_MeasureAndReset(node)
            case _:
                return RewriteResult()

    def rewrite_Measure(
        self, measure_stmt: qubit.MeasureQubit | qubit.MeasureQubitList | wire.Measure
    ) -> RewriteResult:
        if not is_measure_result_used(measure_stmt):
            return RewriteResult()

        qubit_idx_ssas = self.get_qubit_idx_ssas(measure_stmt)
        if qubit_idx_ssas is None:
            return RewriteResult()

        prob_noise_stmt = py.constant.Constant(0.0)
        stim_measure_stmt = stim.collapse.MZ(
            p=prob_noise_stmt.result,
            targets=qubit_idx_ssas,
        )
        prob_noise_stmt.insert_before(measure_stmt)
        measure_stmt.replace_by(stim_measure_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_MeasureAndReset(
        self, meas_and_reset_stmt: qubit.MeasureAndReset | wire.MeasureAndReset
    ) -> RewriteResult:
        if not is_measure_result_used(meas_and_reset_stmt):
            return RewriteResult()

        qubit_idx_ssas = self.get_qubit_idx_ssas(meas_and_reset_stmt)

        if qubit_idx_ssas is None:
            return RewriteResult()

        error_p_stmt = py.Constant(0.0)
        stim_mz_stmt = stim.collapse.MZ(targets=qubit_idx_ssas, p=error_p_stmt.result)
        stim_rz_stmt = stim.collapse.RZ(
            targets=qubit_idx_ssas,
        )

        error_p_stmt.insert_before(meas_and_reset_stmt)
        stim_mz_stmt.insert_before(meas_and_reset_stmt)
        meas_and_reset_stmt.replace_by(stim_rz_stmt)

        return RewriteResult(has_done_something=True)

    def get_qubit_idx_ssas(self, measure_stmt) -> tuple[ir.SSAValue, ...] | None:
        """
        Extract the address attribute and insert qubit indices for the given measure statement.
        """
        match measure_stmt:
            case qubit.MeasureQubit():
                address_attr = measure_stmt.qubit.hints.get("address")
            case qubit.MeasureQubitList():
                address_attr = measure_stmt.qubits.hints.get("address")
            case wire.Measure():
                address_attr = measure_stmt.wire.hints.get("address")
            case _:
                return None

        if address_attr is None:
            return None

        assert isinstance(address_attr, AddressAttribute)

        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=address_attr, stmt_to_insert_before=measure_stmt
        )

        return qubit_idx_ssas
