# create rewrite rule name SquinMeasureToStim using kirin
from dataclasses import dataclass

from kirin import ir
from kirin.analysis import ForwardFrame
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import qubit
from bloqade.stim.dialects import collapse
from bloqade.analysis.address import Address
from bloqade.stim.rewrite.util import (
    insert_qubit_idx_from_address,
)


@dataclass
class SquinMeasureToStim(RewriteRule):
    """
    Rewrite squin measure-related statements to stim statements.
    """

    address_frame: ForwardFrame[Address]

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case qubit.stmts.Measure():
                return self.rewrite_Measure(node)
            case _:
                return RewriteResult()

    def rewrite_Measure(self, measure_stmt: qubit.stmts.Measure) -> RewriteResult:

        address_lattice_elem = self.address_frame.entries.get(measure_stmt.qubits)
        if address_lattice_elem is None:
            return RewriteResult()
        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=address_lattice_elem, stmt_to_insert_before=measure_stmt
        )
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
