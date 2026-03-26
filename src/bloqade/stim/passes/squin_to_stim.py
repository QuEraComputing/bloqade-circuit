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
from kirin.ir.exception import ValidationErrorGroup
from kirin.passes.hint_const import HintConst

from bloqade.stim.rewrite import (
    ScfForToRepeat,
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
from bloqade.rewrite.passes import AggressiveUnroll, CanonicalizeIList
from bloqade.analysis.address import AddressAnalysis
from bloqade.record_idx_helper import dialect as record_idx_helper_dialect
from bloqade.analysis.measure_id import MeasurementIDAnalysis
from bloqade.stim.passes.flatten import Flatten
from bloqade.stim.passes.cleanup_non_stim import RemoveDeadNonStimStatements
from bloqade.stim.passes.hint_const_in_loops import HintConstInLoopBodies
from bloqade.rewrite.passes.aggressive_unroll import Fold as BloqadeFold
from bloqade.stim.analysis.from_squin_validation import StimFromSquinValidation


@dataclass
class SquinToStimPass(Pass):

    def unsafe_run(self, mt: Method) -> RewriteResult:

        rewrite_result = Flatten(dialects=mt.dialects, no_raise=self.no_raise).fixpoint(
            mt
        )

        # Set const hints and propagate address hints inside preserved scf.For bodies.
        # HintConst doesn't enter scf.For body frames, so we need this for
        # downstream passes (ConstantFold, SetDetectorPartial, etc.) to work.
        rewrite_result = (
            Walk(HintConstInLoopBodies()).rewrite(mt.code).join(rewrite_result)
        )

        # Re-fold with the new hints available
        rewrite_result = (
            BloqadeFold(mt.dialects, no_raise=self.no_raise)
            .unsafe_run(mt)
            .join(rewrite_result)
        )

        validation = StimFromSquinValidation()
        _, validation_errors = validation.run(mt)
        if validation_errors:
            raise ValidationErrorGroup(
                f"Stim from Squin validation failed with {len(validation_errors)} error(s)",
                errors=validation_errors,
            )

        address_analysis = AddressAnalysis(dialects=mt.dialects)
        address_analysis_frame, _ = address_analysis.run(mt)

        rewrite_result = (
            Walk(WrapAddressAnalysis(address_analysis=address_analysis_frame.entries))
            .rewrite(mt.code)
            .join(rewrite_result)
        )

        # Propagate hints into preserved scf.For bodies again after address analysis
        rewrite_result = (
            Walk(HintConstInLoopBodies()).rewrite(mt.code).join(rewrite_result)
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

        # --- hint constants inside preserved loop bodies before analysis ---
        # SetDetectorPartial creates new py.Constant stmts inside scf.For bodies
        # that need const hints for MeasurementIDAnalysis to resolve indices.
        rewrite_result = (
            Walk(HintConstInLoopBodies()).rewrite(mt.code).join(rewrite_result)
        )

        # --- analysis (produces RecId for GetRecIdxFromMeasurement / GetRecIdxFromPredicate) ---
        analysis_dialects = mt.dialects.add(record_idx_helper_dialect)
        rewrite_result = (
            HintConst(analysis_dialects, no_raise=self.no_raise)
            .unsafe_run(mt)
            .join(rewrite_result)
        )
        measurement_id_analysis = MeasurementIDAnalysis(dialects=analysis_dialects)
        meas_analysis_frame, _ = measurement_id_analysis.run(mt)

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

        # --- convert eligible scf.For to stim_cf.Repeat ---
        # Runs last: by this point the body is fully in stim dialect.
        rewrite_result = Walk(ScfForToRepeat()).rewrite(mt.code).join(rewrite_result)

        # --- safety net: unroll any remaining scf.For ---
        # Use the full AggressiveUnroll (non-selective) to unroll loops
        # that couldn't become REPEAT. Then re-run conversion passes on
        # the newly expanded code.
        rewrite_result = (
            AggressiveUnroll(mt.dialects, no_raise=True)
            .fixpoint(mt)
            .join(rewrite_result)
        )

        # --- final cleanup after REPEAT conversion ---
        rewrite_result = (
            Fixpoint(
                Walk(
                    Chain(
                        RemoveDeadNonStimStatements(),
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
