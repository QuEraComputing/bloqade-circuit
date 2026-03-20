from dataclasses import field, dataclass

from kirin import ir, types as kirin_types
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.record_idx_helper import GetRecIdxFromMeasurement
from bloqade.stim.dialects.auxiliary import GetRecord, ObservableInclude
from bloqade.decoders.dialects.annotate.stmts import SetObservable


@dataclass
class SetObservablePartial(RewriteRule):
    """Rewrite SetObservable using GetRecIdxFromMeasurement placeholders.

    Instead of computing record indices from analysis results immediately, this injects
    GetRecIdxFromMeasurement statements that will be resolved post-analysis.
    The observable index is assigned by a simple counter based on statement order.
    """

    observable_count: int = field(default=0, init=False)

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if isinstance(node, SetObservable):
            return self.rewrite_SetObservable(node)
        return RewriteResult()

    def rewrite_SetObservable(self, node: SetObservable) -> RewriteResult:
        measurements_type = node.measurements.type
        num_measurements = measurements_type.vars[1]
        if not isinstance(num_measurements, kirin_types.Literal):
            return RewriteResult()

        get_record_ssas = []
        for measurement_idx in range(num_measurements.data):
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

        observable_idx_stmt = py.Constant(self.observable_count)
        observable_idx_stmt.insert_before(node)
        self.observable_count += 1

        observable_include_stmt = ObservableInclude(
            idx=observable_idx_stmt.result, targets=tuple(get_record_ssas)
        )

        node.replace_by(observable_include_stmt)

        return RewriteResult(has_done_something=True)
