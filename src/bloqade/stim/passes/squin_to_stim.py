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

from bloqade.stim.rewrite import (
    PyConstantToStim,
    SquinNoiseToStim,
    SquinQubitToStim,
    SquinMeasureToStim,
)
from bloqade.squin.rewrite import (
    SquinU3ToClifford,
    RemoveDeadRegister,
    WrapAddressAnalysis,
)
from bloqade.rewrite.passes import CanonicalizeIList
from bloqade.analysis.address import AddressAnalysis
from bloqade.analysis.measure_id import MeasurementIDAnalysis
from bloqade.stim.passes.flatten import Flatten

from ..rewrite import IfToStim, SetDetectorToStim, SetObservableToStim


@dataclass
class SquinToStimPass(Pass):

    def unsafe_run(self, mt: Method) -> RewriteResult:

        # inline aggressively:
        rewrite_result = Flatten(dialects=mt.dialects, no_raise=self.no_raise).fixpoint(
            mt
        )

        # after this the program should be in a state where it is analyzable
        # -------------------------------------------------------------------

        mia = MeasurementIDAnalysis(dialects=mt.dialects)
        meas_analysis_frame, _ = mia.run(mt)

        aa = AddressAnalysis(dialects=mt.dialects)
        address_analysis_frame, _ = aa.run(mt)

        # wrap the address analysis result
        rewrite_result = (
            Walk(WrapAddressAnalysis(address_analysis=address_analysis_frame.entries))
            .rewrite(mt.code)
            .join(rewrite_result)
        )

        # 2. rewrite
        ## Invoke DCE afterwards to eliminate any GetItems
        ## that are no longer being used. This allows for
        ## SquinMeasureToStim to safely eliminate
        ## unused measure statements.
        rewrite_result = (
            Chain(
                Walk(IfToStim(measure_frame=meas_analysis_frame)),
                Walk(SetDetectorToStim(measure_id_frame=meas_analysis_frame)),
                Walk(SetObservableToStim(measure_id_frame=meas_analysis_frame)),
                Fixpoint(Walk(DeadCodeElimination())),
            )
            .rewrite(mt.code)
            .join(rewrite_result)
        )

        # Rewrite the noise statements first.
        rewrite_result = Walk(SquinNoiseToStim()).rewrite(mt.code).join(rewrite_result)

        # Wrap Rewrite + SquinToStim can happen w/ standard walk
        rewrite_result = Walk(SquinU3ToClifford()).rewrite(mt.code).join(rewrite_result)

        rewrite_result = (
            Walk(
                Chain(
                    SquinQubitToStim(),
                    SquinMeasureToStim(),
                )
            )
            .rewrite(mt.code)
            .join(rewrite_result)
        )

        rewrite_result = (
            CanonicalizeIList(dialects=mt.dialects, no_raise=self.no_raise)
            .unsafe_run(mt)
            .join(rewrite_result)
        )

        # Convert all PyConsts to Stim Constants
        rewrite_result = Walk(PyConstantToStim()).rewrite(mt.code).join(rewrite_result)

        # clear up leftover stmts
        # - remove any squin.qalloc that's left around
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
