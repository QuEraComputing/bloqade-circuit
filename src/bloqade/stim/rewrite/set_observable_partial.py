from dataclasses import dataclass

from kirin import ir, types as kirin_types
from kirin.dialects import py, scf
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.record_idx_helper import GetRecIdxFromMeasurement
from bloqade.analysis.observable_idx import ObservableIdxFrame
from bloqade.stim.dialects.auxiliary import GetRecord, ObservableInclude
from bloqade.decoders.dialects.annotate.stmts import SetObservable


@dataclass
class SetObservablePartial(RewriteRule):
    """Rewrite SetObservable using GetRecIdxFromMeasurement placeholders.

    Instead of computing record indices from analysis results immediately, this injects
    GetRecIdxFromMeasurement statements that will be resolved post-analysis.
    Observable indices come from ObservableIdxAnalysis so partial and resolve
    rewrites share a single namespace.
    """

    obs_idx_frame: ObservableIdxFrame

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if isinstance(node, SetObservable):
            return self.rewrite_SetObservable(node)
        return RewriteResult()

    def rewrite_SetObservable(self, node: SetObservable) -> RewriteResult:
        # Bail to ResolveSetObservable when measurements comes from an scf.For
        # result: the type info is collapsed to init.type by
        # PropagateInitializerHints, so vars[1] lies about the true length for
        # loop-grown accumulators.
        if isinstance(node.measurements.owner, scf.For):
            return RewriteResult()

        measurements_type = node.measurements.type
        if not (
            isinstance(measurements_type, kirin_types.Generic)
            and len(measurements_type.vars) >= 2
            and isinstance(measurements_type.vars[1], kirin_types.Literal)
        ):
            return RewriteResult()
        num_measurements = measurements_type.vars[1]

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

        observable_idx_stmt = py.Constant(
            self.obs_idx_frame.observable_idx_at_stmt[node]
        )
        observable_idx_stmt.insert_before(node)

        observable_include_stmt = ObservableInclude(
            idx=observable_idx_stmt.result, targets=tuple(get_record_ssas)
        )

        node.replace_by(observable_include_stmt)

        return RewriteResult(has_done_something=True)
