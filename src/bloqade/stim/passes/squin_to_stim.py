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

from bloqade.stim.groups import main as stim_main
from bloqade.stim.rewrite import (
    ScfForToRepeat,
    IfToStimPartial,
    SquinGateToStim,
    PyConstantToStim,
    ResolveGetRecIdx,
    SquinNoiseToStim,
    SquinResetToStim,
    ResolveSetDetector,
    SetDetectorPartial,
    SquinMeasureToStim,
    ResolveSetObservable,
    SetObservablePartial,
)
from bloqade.squin.rewrite import SquinU3ToClifford
from bloqade.rewrite.passes import CanonicalizeIList
from bloqade.analysis.address import AddressAnalysis
from bloqade.record_idx_helper import dialect as record_idx_helper_dialect
from bloqade.analysis.measure_id import MeasurementIDAnalysis
from bloqade.stim.passes.flatten import Flatten
from bloqade.stim.passes.cleanup_non_stim import RemoveDeadNonStimStatements
from bloqade.stim.passes.constprop_override import StimHintConst
from bloqade.stim.passes.hint_const_in_loops import HintConstInLoops
from bloqade.stim.analysis.from_squin_validation import StimFromSquinValidation


@dataclass
class SquinToStimPass(Pass):

    def unsafe_run(self, mt: Method) -> RewriteResult:

        rewrite_result = Flatten(dialects=mt.dialects, no_raise=self.no_raise).fixpoint(
            mt
        )

        validation = StimFromSquinValidation()
        _, validation_errors = validation.run(mt)
        if validation_errors:
            raise ValidationErrorGroup(
                f"Stim from Squin validation failed with {len(validation_errors)} error(s)",
                errors=validation_errors,
            )

        address_analysis = AddressAnalysis(dialects=mt.dialects)
        addresses = address_analysis.run(mt)[0].entries

        # --- squin-to-stim rewrites ---
        hint_const_in_loops = HintConstInLoops(self.dialects, no_raise=self.no_raise)

        # propagate types/hints into preserved loop bodies
        rewrite_result = hint_const_in_loops.unsafe_run(mt).join(rewrite_result)

        # partial rewrites (inject GetRecIdx helpers)
        rewrite_result = (
            Walk(
                Chain(
                    SetDetectorPartial(),
                    SetObservablePartial(),
                    IfToStimPartial(address_analysis=addresses),
                )
            )
            .rewrite(mt.code)
            .join(rewrite_result)
        )

        # dialect conversions
        rewrite_result = (
            Chain(
                Walk(SquinNoiseToStim(address_analysis=addresses)),
                Walk(SquinU3ToClifford()),
                Walk(SquinResetToStim(address_analysis=addresses)),
                Walk(SquinGateToStim(address_analysis=addresses)),
            )
            .rewrite(mt.code)
            .join(rewrite_result)
        )

        # re-hint after partial rewrites created new py.Constant stmts
        rewrite_result = hint_const_in_loops.unsafe_run(mt).join(rewrite_result)

        # --- measurement ID analysis ---
        analysis_dialects = mt.dialects.add(record_idx_helper_dialect)
        rewrite_result = (
            StimHintConst(analysis_dialects, no_raise=self.no_raise)
            .unsafe_run(mt)
            .join(rewrite_result)
        )
        meas_analysis_frame = MeasurementIDAnalysis(dialects=analysis_dialects).run(mt)[
            0
        ]

        # --- resolve record indices + remaining conversions ---
        rewrite_result = (
            Chain(
                Walk(ResolveGetRecIdx(measure_id_frame=meas_analysis_frame)),
                Walk(ResolveSetObservable(measure_id_frame=meas_analysis_frame)),
                Walk(ResolveSetDetector(measure_id_frame=meas_analysis_frame)),
                Fixpoint(Walk(DeadCodeElimination())),
                Walk(SquinMeasureToStim(address_analysis=addresses)),
            )
            .rewrite(mt.code)
            .join(rewrite_result)
        )

        rewrite_result = (
            CanonicalizeIList(dialects=mt.dialects, no_raise=self.no_raise)
            .unsafe_run(mt)
            .join(rewrite_result)
        )

        # --- REPEAT conversion + cleanup ---
        rewrite_result = (
            Chain(
                Walk(PyConstantToStim()),
                Walk(ScfForToRepeat()),
                Fixpoint(
                    Walk(
                        Chain(
                            DeadCodeElimination(),
                            CommonSubexpressionElimination(),
                            RemoveDeadNonStimStatements(keep=stim_main),
                        )
                    )
                ),
            )
            .rewrite(mt.code)
            .join(rewrite_result)
        )

        return rewrite_result
