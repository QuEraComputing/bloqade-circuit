from dataclasses import dataclass

from kirin.rewrite import (
    Walk,
    Chain,
    Fixpoint,
    DeadCodeElimination,
    CommonSubexpressionElimination,
)
from kirin.ir.method import Method
from kirin.passes.abc import Pass
from kirin.rewrite.abc import RewriteResult
from kirin.passes.hint_const import HintConst

from bloqade.stim.rewrite import (
    IfToStimPartial,
    PyConstantToStim,
    ResolveGetRecIdx,
    SquinNoiseToStim,
    SquinQubitToStim,
    SetDetectorPartial,
    SquinMeasureToStim,
    SetObservablePartial,
)
from bloqade.squin.rewrite import (
    SquinU3ToClifford,
    RemoveDeadRegister,
    WrapAddressAnalysis,
)
from bloqade.rewrite.passes import CanonicalizeIList
from bloqade.analysis.address import AddressAnalysis
from bloqade.record_idx_helper import dialect as record_idx_helper_dialect
from bloqade.analysis.measure_id import MeasurementIDAnalysis
from bloqade.stim.passes.flatten import Flatten


@dataclass
class SquinToStimPass(Pass):

    def unsafe_run(self, mt: Method) -> RewriteResult:

        rewrite_result = Flatten(dialects=mt.dialects, no_raise=self.no_raise).fixpoint(
            mt
        )

        aa = AddressAnalysis(dialects=mt.dialects)
        address_analysis_frame, _ = aa.run(mt)

        rewrite_result = (
            Walk(WrapAddressAnalysis(address_analysis=address_analysis_frame.entries))
            .rewrite(mt.code)
            .join(rewrite_result)
        )

        # --- partial rewrite (before analysis) ---
        rewrite_result = (
            Walk(
                Chain(
                    SetDetectorPartial(),
                    SetObservablePartial(),
                    IfToStimPartial(),
                )
            )
            .rewrite(mt.code)
            .join(rewrite_result)
        )

        rewrite_result = Walk(SquinNoiseToStim()).rewrite(mt.code).join(rewrite_result)
        rewrite_result = Walk(SquinU3ToClifford()).rewrite(mt.code).join(rewrite_result)
        rewrite_result = Walk(SquinQubitToStim()).rewrite(mt.code).join(rewrite_result)

        # --- analysis (produces RecId for GetRecIdxFromMeasurement / GetRecIdxFromPredicate) ---
        analysis_dialects = mt.dialects.add(record_idx_helper_dialect)
        rewrite_result = (
            HintConst(analysis_dialects, no_raise=self.no_raise)
            .unsafe_run(mt)
            .join(rewrite_result)
        )
        mia = MeasurementIDAnalysis(dialects=analysis_dialects)
        meas_analysis_frame, _ = mia.run(mt)

        # --- post-analysis: resolve helper stmts into direct integer constants ---
        rewrite_result = (
            Chain(
                Walk(ResolveGetRecIdx(measure_id_frame=meas_analysis_frame)),
                Fixpoint(Walk(DeadCodeElimination())),
            )
            .rewrite(mt.code)
            .join(rewrite_result)
        )

        # --- rewrite measures (must stay until after analysis) ---
        rewrite_result = (
            Walk(SquinMeasureToStim()).rewrite(mt.code).join(rewrite_result)
        )

        rewrite_result = (
            CanonicalizeIList(dialects=mt.dialects, no_raise=self.no_raise)
            .unsafe_run(mt)
            .join(rewrite_result)
        )

        rewrite_result = Walk(PyConstantToStim()).rewrite(mt.code).join(rewrite_result)

        rewrite_result = (
            Fixpoint(
                Walk(
                    Chain(
                        DeadCodeElimination(),
                        CommonSubexpressionElimination(),
                        RemoveDeadRegister(),
                    )
                )
            )
            .rewrite(mt.code)
            .join(rewrite_result)
        )

        return rewrite_result
