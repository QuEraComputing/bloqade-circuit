# create rewrite rule name SquinMeasureToStim using kirin
from dataclasses import dataclass

from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin import qubit
from bloqade.squin.rewrite import AddressAttribute
from bloqade.stim.dialects import collapse
from bloqade.stim.rewrite.util import (
    insert_qubit_idx_from_address,
)


@dataclass
class SquinMeasureToStim(RewriteRule):
    """
    Rewrite squin measure-related statements to stim statements.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case qubit.MeasureQubit() | qubit.MeasureQubitList():
                return self.rewrite_Measure(node)
            case _:
                return RewriteResult()

    def rewrite_Measure(
        self, measure_stmt: qubit.MeasureQubit | qubit.MeasureQubitList
    ) -> RewriteResult:

        qubit_idx_ssas = self.get_qubit_idx_ssas(measure_stmt)
        if qubit_idx_ssas is None:
            return RewriteResult()

        prob_noise_stmt = py.constant.Constant(0.0)
        stim_measure_stmt = collapse.MZ(
            p=prob_noise_stmt.result,
            targets=qubit_idx_ssas,
        )
        prob_noise_stmt.insert_before(measure_stmt)
        stim_measure_stmt.insert_before(measure_stmt)

        # if the measurement is not being used anywhere
        # we can safely get rid of it. Measure cannot be DCE'd because
        # it is not pure.
        if not bool(measure_stmt.result.uses):
            measure_stmt.delete()

        return RewriteResult(has_done_something=True)

    def get_qubit_idx_ssas(
        self, measure_stmt: qubit.MeasureQubit | qubit.MeasureQubitList
    ) -> tuple[ir.SSAValue, ...] | None:
        """
        Extract the address attribute and insert qubit indices for the given measure statement.
        """
        match measure_stmt:
            case qubit.MeasureQubit():
                address_attr = measure_stmt.qubit.hints.get("address")
            case qubit.MeasureQubitList():
                address_attr = measure_stmt.qubits.hints.get("address")
            case _:
                return None

        if address_attr is None:
            return None

        assert isinstance(address_attr, AddressAttribute)

        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=address_attr, stmt_to_insert_before=measure_stmt
        )

        return qubit_idx_ssas
