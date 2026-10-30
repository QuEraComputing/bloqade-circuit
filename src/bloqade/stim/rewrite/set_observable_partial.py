from dataclasses import dataclass

from kirin import ir
from kirin.dialects import py, scf
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.record_idx_helper import GetRecIdxFromMeasurement
from bloqade.analysis.measure_id import MeasureIDFrame
from bloqade.analysis.observable_idx import ObservableIdxFrame
from bloqade.stim.dialects.auxiliary import GetRecord, ObservableInclude
from bloqade.stim.rewrite.get_record_util import measurement_count
from bloqade.decoders.dialects.annotate.stmts import SetObservable


@dataclass
class SetObservablePartial(RewriteRule):
    """Rewrite SetObservable using GetRecIdxFromMeasurement placeholders.

    Instead of computing record indices from analysis results immediately, this injects
    GetRecIdxFromMeasurement statements that will be resolved post-analysis.
    Observable indices come from ObservableIdxAnalysis so partial and resolve
    rewrites share a single namespace. `measure_id_frame` gives the number of
    measurements, as `measurement_count` describes.
    """

    obs_idx_frame: ObservableIdxFrame
    measure_id_frame: MeasureIDFrame | None = None

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Rewrite `node` if it is a `SetObservable`."""
        if isinstance(node, SetObservable):
            return self.rewrite_SetObservable(node)
        return RewriteResult()

    def rewrite_SetObservable(self, node: SetObservable) -> RewriteResult:
        """Replace `node` with an `ObservableInclude` that reads each measurement record.

        The rule leaves `node` if a loop returns its measurements, or if the number
        of measurements is unknown.
        """
        # A list that an scf.For returns holds the measurements of every
        # iteration. ResolveSetAnnotate resolves it later from the concrete
        # measurement IDs of the analysis, so this rule leaves it.
        if isinstance(node.measurements.owner, scf.For):
            return RewriteResult()

        num_measurements = measurement_count(node.measurements, self.measure_id_frame)
        if num_measurements is None:
            return RewriteResult()

        get_record_ssas = []
        for measurement_idx in range(num_measurements):
            idx_const = py.Constant(measurement_idx)
            idx_const.insert_before(node)

            getitem_stmt = py.GetItem(obj=node.measurements, index=idx_const.result)
            getitem_stmt.insert_before(node)

            idx_from_measurement_calc = GetRecIdxFromMeasurement(
                measurement=getitem_stmt.result
            )
            idx_from_measurement_calc.insert_before(node)

            get_record_stmt = GetRecord(id=idx_from_measurement_calc.result)
            get_record_stmt.insert_before(node)

            get_record_ssas.append(get_record_stmt.result)

        observable_idx_stmt = py.Constant(
            self.obs_idx_frame.observable_idx_at_stmt[node]
        )
        observable_idx_stmt.insert_before(node)

        observable_include_stmt = ObservableInclude(
            idx=observable_idx_stmt.result, targets=tuple(get_record_ssas)
        )

        node.replace_by(observable_include_stmt)

        return RewriteResult(has_done_something=True)
