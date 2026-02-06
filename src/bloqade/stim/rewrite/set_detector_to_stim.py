from dataclasses import dataclass

from kirin import ir, types as kirin_types
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.stim.dialects import auxiliary
from bloqade.analysis.measure_id import MeasureIDFrame
from bloqade.stim.dialects.auxiliary import Detector
from bloqade.analysis.measure_id.lattice import DetectorId, RawMeasureId, MeasureIdTuple
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
        detector_id = self.measure_id_frame.entries.get(node.result, None)
        if detector_id is None or not isinstance(detector_id, DetectorId):
            return RewriteResult()

        if not detector_id.coordinates:
            return RewriteResult()

        coord_ssas = []
        for value in detector_id.coordinates:
            coord_stmt = python_num_val_to_stim_const(value)
            if coord_stmt is None:
                return RewriteResult()
            coord_ssas.append(coord_stmt.result)
            coord_stmt.insert_before(node)

        measure_ids = detector_id.data
        if not isinstance(measure_ids, MeasureIdTuple):
            return RewriteResult()

        if not kirin_types.is_tuple_of(
            measure_ids_data := measure_ids.data, RawMeasureId
        ):
            return RewriteResult()

        get_record_list = insert_get_records(
            node, tuple_raw_measure_id=measure_ids_data
        )

        detector_stmt = Detector(
            coord=tuple(coord_ssas), targets=tuple(get_record_list)
        )

        node.replace_by(detector_stmt)

        return RewriteResult(has_done_something=True)
