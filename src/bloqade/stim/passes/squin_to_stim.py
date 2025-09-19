from dataclasses import dataclass

from kirin.passes import Fold, TypeInfer
from kirin.rewrite import (
    Walk,
    Chain,
    Fixpoint,
    CFGCompactify,
    DeadCodeElimination,
    CommonSubexpressionElimination,
)
from kirin.dialects import ilist
from kirin.ir.method import Method
from kirin.passes.abc import Pass
from kirin.rewrite.abc import RewriteResult
from kirin.passes.inline import InlinePass
from kirin.rewrite.alias import InlineAlias
from kirin.passes.aggressive import UnrollScf

from bloqade.stim.rewrite import (
    SquinWireToStim,
    PyConstantToStim,
    SquinNoiseToStim,
    SquinQubitToStim,
    SquinMeasureToStim,
    SquinWireIdentityElimination,
)
from bloqade.squin.rewrite import (
    SquinU3ToClifford,
    RemoveDeadRegister,
    WrapAddressAnalysis,
)
from bloqade.rewrite.passes import CanonicalizeIList
from bloqade.analysis.address import AddressAnalysis
from bloqade.analysis.measure_id import MeasurementIDAnalysis
from bloqade.squin.rewrite.desugar import ApplyDesugarRule, MeasureDesugarRule

from .simplify_ifs import StimSimplifyIfs
from ..rewrite.ifs_to_stim import IfToStim


@dataclass
class SquinToStimPass(Pass):

    def unsafe_run(self, mt: Method) -> RewriteResult:

        # inline aggressively:
        rewrite_result = InlinePass(
            dialects=mt.dialects, no_raise=self.no_raise
        ).unsafe_run(mt)

        rewrite_result = Walk(ilist.rewrite.HintLen()).rewrite(mt.code)
        rewrite_result = Fold(self.dialects).unsafe_run(mt).join(rewrite_result)

        rewrite_result = (
            UnrollScf(dialects=mt.dialects, no_raise=self.no_raise)
            .fixpoint(mt)
            .join(rewrite_result)
        )

        rewrite_result = (
            Walk(Fixpoint(CFGCompactify())).rewrite(mt.code).join(rewrite_result)
        )

        rewrite_result = Walk(InlineAlias()).rewrite(mt.code).join(rewrite_result)

        rewrite_result = (
            StimSimplifyIfs(mt.dialects, no_raise=self.no_raise)
            .unsafe_run(mt)
            .join(rewrite_result)
        )

        rewrite_result = (
            Walk(Chain(ilist.rewrite.ConstList2IList(), ilist.rewrite.Unroll()))
            .rewrite(mt.code)
            .join(rewrite_result)
        )
        rewrite_result = Fold(mt.dialects, no_raise=self.no_raise)(mt)

        rewrite_result = (
            UnrollScf(mt.dialects, no_raise=self.no_raise)
            .fixpoint(mt)
            .join(rewrite_result)
        )

        rewrite_result = (
            CanonicalizeIList(dialects=mt.dialects, no_raise=self.no_raise)
            .unsafe_run(mt)
            .join(rewrite_result)
        )

        rewrite_result = TypeInfer(
            dialects=mt.dialects, no_raise=self.no_raise
        ).unsafe_run(mt)

        rewrite_result = (
            Walk(
                Chain(
                    ApplyDesugarRule(),
                    MeasureDesugarRule(),
                )
            )
            .rewrite(mt.code)
            .join(rewrite_result)
        )

        # after this the program should be in a state where it is analyzable
        # -------------------------------------------------------------------

        mia = MeasurementIDAnalysis(dialects=mt.dialects)
        meas_analysis_frame, _ = mia.run_analysis(mt, no_raise=self.no_raise)

        aa = AddressAnalysis(dialects=mt.dialects)
        address_analysis_frame, _ = aa.run_analysis(mt, no_raise=self.no_raise)

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
                    SquinWireToStim(),
                    SquinWireIdentityElimination(),
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
        # - remove any squin.qubit.new that's left around
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
