# create rewrite rule name SquinMeasureToStim using kirin
from dataclasses import dataclass

from kirin import ir
from kirin.dialects import py, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin import wire, qubit
from bloqade.squin.rewrite import AddressAttribute
from bloqade.stim.dialects import collapse, auxiliary
from bloqade.stim.rewrite.util import (
    is_measure_result_used,
    insert_qubit_idx_from_address,
)
from bloqade.analysis.measure_id.lattice import MeasureId, MeasureIdBool, MeasureIdTuple


def replace_get_record(
    node: ir.Statement, measure_id_bool: MeasureIdBool, meas_count: int
):
    assert isinstance(measure_id_bool, MeasureIdBool)
    target_rec_idx = (measure_id_bool.idx - 1) - meas_count
    idx_stmt = py.constant.Constant(target_rec_idx)
    idx_stmt.insert_before(node)
    get_record_stmt = auxiliary.GetRecord(idx_stmt.result)
    node.replace_by(get_record_stmt)


def insert_get_record_list(
    node: ir.Statement, measure_id_tuple: MeasureIdTuple, meas_count: int
):
    """
    Insert GetRecord statements before the given node
    """
    get_record_ssas = []
    for measure_id_bool in measure_id_tuple.data:
        assert isinstance(measure_id_bool, MeasureIdBool)
        target_rec_idx = (measure_id_bool.idx - 1) - meas_count
        idx_stmt = py.constant.Constant(target_rec_idx)
        idx_stmt.insert_before(node)
        get_record_stmt = auxiliary.GetRecord(idx_stmt.result)
        get_record_stmt.insert_before(node)
        get_record_ssas.append(get_record_stmt.result)

    node.replace_by(ilist.New(values=get_record_ssas))


@dataclass
class SquinMeasureToStim(RewriteRule):
    """
    Rewrite squin measure-related statements to stim statements.
    """

    measure_id_result: dict[ir.SSAValue, MeasureId]
    total_measure_count: int

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case qubit.MeasureQubit() | qubit.MeasureQubitList() | wire.Measure():
                return self.rewrite_Measure(node)
            case _:
                return RewriteResult()

    def rewrite_Measure(
        self, measure_stmt: qubit.MeasureQubit | qubit.MeasureQubitList | wire.Measure
    ) -> RewriteResult:

        qubit_idx_ssas = self.get_qubit_idx_ssas(measure_stmt)
        if qubit_idx_ssas is None:
            return RewriteResult()

        measure_id = self.measure_id_result[measure_stmt.result]
        if not isinstance(measure_id, (MeasureIdBool, MeasureIdTuple)):
            return RewriteResult()

        prob_noise_stmt = py.constant.Constant(0.0)
        stim_measure_stmt = collapse.MZ(
            p=prob_noise_stmt.result,
            targets=qubit_idx_ssas,
        )
        prob_noise_stmt.insert_before(measure_stmt)
        stim_measure_stmt.insert_before(measure_stmt)

        if not is_measure_result_used(measure_stmt):
            measure_stmt.delete()
            return RewriteResult(has_done_something=True)

        # replace dataflow with new stmt!
        measure_id = self.measure_id_result[measure_stmt.result]
        if isinstance(measure_id, MeasureIdBool):
            replace_get_record(
                node=measure_stmt,
                measure_id_bool=measure_id,
                meas_count=self.total_measure_count,
            )
        elif isinstance(measure_id, MeasureIdTuple):
            insert_get_record_list(
                node=measure_stmt,
                measure_id_tuple=measure_id,
                meas_count=self.total_measure_count,
            )
        else:
            # already checked before, so this should not happen
            raise ValueError(
                f"Unexpected measure ID type: {type(measure_id)} for measure statement {measure_stmt}"
            )

        return RewriteResult(has_done_something=True)

    def get_qubit_idx_ssas(
        self, measure_stmt: qubit.MeasureQubit | qubit.MeasureQubitList | wire.Measure
    ) -> tuple[ir.SSAValue, ...] | None:
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
