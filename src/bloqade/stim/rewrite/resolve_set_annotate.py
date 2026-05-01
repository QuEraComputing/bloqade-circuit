from dataclasses import dataclass

from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.analysis.measure_id import MeasureIDFrame
from bloqade.analysis.observable_idx import ObservableIdxFrame
from bloqade.stim.dialects.auxiliary import Detector, GetRecord, ObservableInclude
from bloqade.analysis.measure_id.lattice import (
    RawMeasureId,
    MeasureIdBool,
    MeasureIdTuple,
)
from bloqade.decoders.dialects.annotate.stmts import SetDetector, SetObservable
from bloqade.stim.rewrite.set_detector_partial import extract_coord_ssas


@dataclass
class ResolveSetAnnotate(RewriteRule):
    """Expand SetObservable / SetDetector statements that survived the
    partial rewrites' scf.For-owner guard.

    Runs post-MeasurementIDAnalysis. Reads MeasureIdTuple directly from the
    analysis frame and computes record indices without going through
    GetRecIdxFromMeasurement placeholders. Applicable when concrete
    RawMeasureId (or MeasureIdBool) entries survive in frame — true for
    scf.For result SSAs consumed outside the loop. Observable indices come
    from ObservableIdxAnalysis to share a single namespace with
    SetObservablePartial.
    """

    measure_id_frame: MeasureIDFrame
    obs_idx_frame: ObservableIdxFrame

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if isinstance(node, SetObservable):
            return self._resolve_observable(node)
        if isinstance(node, SetDetector):
            return self._resolve_detector(node)
        return RewriteResult()

    def _build_get_record_chain(
        self, node: ir.Statement, measurements: ir.SSAValue
    ) -> list[ir.SSAValue] | None:
        """Emit py.Constant + GetRecord chain for each measurement in the
        frame's MeasureIdTuple. Returns the GetRecord result SSAs, or None
        if the frame state isn't usable (aggregate hasn't been analyzed into
        a concrete MeasureIdTuple, num_measures_at_stmt missing, or an
        element isn't a concrete RawMeasureId / MeasureIdBool).
        """
        tup = self.measure_id_frame.entries.get(measurements)
        if not isinstance(tup, MeasureIdTuple):
            return None

        num_measures_here = self.measure_id_frame.num_measures_at_stmt.get(node)
        if num_measures_here is None:
            return None

        get_record_ssas: list[ir.SSAValue] = []
        for elem in tup.data:
            if not isinstance(elem, (RawMeasureId, MeasureIdBool)):
                return None
            rec_idx = (elem.idx - 1) - num_measures_here
            idx_const = py.Constant(rec_idx)
            idx_const.insert_before(node)
            get_record = GetRecord(id=idx_const.result)
            get_record.insert_before(node)
            get_record_ssas.append(get_record.result)

        return get_record_ssas

    def _resolve_observable(self, node: SetObservable) -> RewriteResult:
        get_record_ssas = self._build_get_record_chain(node, node.measurements)
        if get_record_ssas is None:
            return RewriteResult()

        obs_idx_const = py.Constant(self.obs_idx_frame.observable_idx_at_stmt[node])
        obs_idx_const.insert_before(node)

        node.replace_by(
            ObservableInclude(idx=obs_idx_const.result, targets=tuple(get_record_ssas))
        )
        return RewriteResult(has_done_something=True)

    def _resolve_detector(self, node: SetDetector) -> RewriteResult:
        coord_ssas = extract_coord_ssas(node)
        if coord_ssas is None:
            return RewriteResult()

        get_record_ssas = self._build_get_record_chain(node, node.measurements)
        if get_record_ssas is None:
            return RewriteResult()

        node.replace_by(
            Detector(coord=tuple(coord_ssas), targets=tuple(get_record_ssas))
        )
        return RewriteResult(has_done_something=True)
