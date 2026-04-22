from dataclasses import dataclass

from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.analysis.measure_id import MeasureIDFrame
from bloqade.stim.dialects.auxiliary import Detector, GetRecord
from bloqade.analysis.measure_id.lattice import (
    RawMeasureId,
    MeasureIdBool,
    MeasureIdTuple,
)
from bloqade.decoders.dialects.annotate.stmts import SetDetector
from bloqade.stim.rewrite.set_detector_partial import extract_coord_ssas


@dataclass
class ResolveSetDetector(RewriteRule):
    """Expand SetDetector statements that survived SetDetectorPartial.

    Runs post-MeasurementIDAnalysis. Reads MeasureIdTuple directly from the
    analysis frame and computes record indices without going through
    GetRecIdxFromMeasurement placeholders.
    """

    measure_id_frame: MeasureIDFrame

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if isinstance(node, SetDetector):
            return self._resolve(node)
        return RewriteResult()

    def _resolve(self, node: SetDetector) -> RewriteResult:
        tup = self.measure_id_frame.entries.get(node.measurements)
        if not isinstance(tup, MeasureIdTuple):
            return RewriteResult()

        num_measures_here = self.measure_id_frame.num_measures_at_stmt.get(node)
        if num_measures_here is None:
            return RewriteResult()

        coord_ssas = extract_coord_ssas(node)
        if coord_ssas is None:
            return RewriteResult()

        get_record_ssas = []
        for elem in tup.data:
            if not isinstance(elem, (RawMeasureId, MeasureIdBool)):
                return RewriteResult()
            rec_idx = (elem.idx - 1) - num_measures_here
            idx_const = py.Constant(rec_idx)
            idx_const.insert_before(node)
            get_record = GetRecord(id=idx_const.result)
            get_record.insert_before(node)
            get_record_ssas.append(get_record.result)

        detector = Detector(coord=tuple(coord_ssas), targets=tuple(get_record_ssas))
        node.replace_by(detector)
        return RewriteResult(has_done_something=True)
