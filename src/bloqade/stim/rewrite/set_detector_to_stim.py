from dataclasses import dataclass

from kirin import ir
from kirin.dialects import py, ilist
from kirin.dialects.py import Constant
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.stim.dialects import auxiliary
from bloqade.analysis.measure_id import MeasureIDFrame
from bloqade.stim.dialects.auxiliary import Detector
from bloqade.analysis.measure_id.lattice import DetectorId, MeasureIdTuple
from bloqade.decoders.dialects.annotate.stmts import SetDetector

from ..rewrite.get_record_util import insert_get_records


def python_num_val_to_stim_const(value: int | float) -> ir.Statement | None:
    if isinstance(value, float):
        const_stmt = auxiliary.ConstFloat(value=value)
    elif isinstance(value, int):
        const_stmt = auxiliary.ConstInt(value=value)
    else:
        return None

    return const_stmt


@dataclass
class SetDetectorToStim(RewriteRule):
    """
    Rewrite SetDetector to GetRecord and Detector in the stim dialect
    """

    measure_id_frame: MeasureIDFrame

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        match node:
            case SetDetector():
                return self.rewrite_SetDetector(node)
            case _:
                return RewriteResult()

    def rewrite_SetDetector(self, node: SetDetector) -> RewriteResult:

        coord_ssas = []

        # coordinates can be a py.Constant with an ilist or a raw ilist
        if not isinstance(node.coordinates.owner, (ilist.New, py.Constant)):
            return RewriteResult()

        if isinstance(node.coordinates.owner, ilist.New):
            coord_values_ssas = node.coordinates.owner.values
            for coord_value_ssa in coord_values_ssas:
                if isinstance(coord_value_ssa.owner, Constant):
                    value = coord_value_ssa.owner.value.unwrap()
                    coord_stmt = python_num_val_to_stim_const(value)
                    if coord_stmt is None:
                        return RewriteResult()
                    coord_ssas.append(coord_stmt.result)
                    coord_stmt.insert_before(node)
                else:
                    return RewriteResult()

        if isinstance(node.coordinates.owner, py.Constant):
            const_value = node.coordinates.owner.value.unwrap()
            if not isinstance(const_value, ilist.IList):
                return RewriteResult()
            ilist_value = const_value.data
            if not isinstance(ilist_value, list):
                return RewriteResult()
            for value in ilist_value:
                coord_stmt = python_num_val_to_stim_const(value)
                if coord_stmt is None:
                    return RewriteResult()
                coord_ssas.append(coord_stmt.result)
                coord_stmt.insert_before(node)

        detector_id = self.measure_id_frame.entries.get(node.result, None)
        if detector_id is None or not isinstance(detector_id, DetectorId):
            return RewriteResult()

        measure_ids = detector_id.data
        if not isinstance(measure_ids, MeasureIdTuple):
            return RewriteResult()

        get_record_list = insert_get_records(node, measure_ids)

        detector_stmt = Detector(
            coord=tuple(coord_ssas), targets=tuple(get_record_list)
        )

        node.replace_by(detector_stmt)

        return RewriteResult(has_done_something=True)
