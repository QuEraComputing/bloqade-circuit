from dataclasses import field, dataclass

from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.analysis.measure_id import MeasureIDFrame
from bloqade.stim.dialects.auxiliary import GetRecord, ObservableInclude
from bloqade.analysis.measure_id.lattice import (
    RawMeasureId,
    MeasureIdBool,
    MeasureIdTuple,
)
from bloqade.decoders.dialects.annotate.stmts import SetObservable


@dataclass
class ResolveSetObservable(RewriteRule):
    """Expand SetObservable statements that survived SetObservablePartial.

    Runs post-MeasurementIDAnalysis. Reads MeasureIdTuple directly from the
    analysis frame and computes record indices without going through
    GetRecIdxFromMeasurement placeholders. Applicable when concrete
    RawMeasureId (or MeasureIdBool) entries survive in frame — true for
    scf.For result SSAs consumed outside the loop.
    """

    measure_id_frame: MeasureIDFrame
    observable_count: int = field(default=0, init=False)

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if isinstance(node, SetObservable):
            return self._resolve(node)
        return RewriteResult()

    def _resolve(self, node: SetObservable) -> RewriteResult:
        tup = self.measure_id_frame.entries.get(node.measurements)
        if not isinstance(tup, MeasureIdTuple):
            return RewriteResult()

        num_measures_here = self.measure_id_frame.num_measures_at_stmt.get(node)
        if num_measures_here is None:
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

        obs_idx_const = py.Constant(self.observable_count)
        obs_idx_const.insert_before(node)
        self.observable_count += 1

        observable_include = ObservableInclude(
            idx=obs_idx_const.result, targets=tuple(get_record_ssas)
        )
        node.replace_by(observable_include)
        return RewriteResult(has_done_something=True)
