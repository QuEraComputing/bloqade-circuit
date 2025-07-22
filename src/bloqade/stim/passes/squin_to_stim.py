from dataclasses import dataclass

from kirin.passes import Fold, HintConst
from kirin.rewrite import (
    Walk,
    Chain,
    Fixpoint,
    CFGCompactify,
    InlineGetItem,
    InlineGetField,
    DeadCodeElimination,
    CommonSubexpressionElimination,
)
from kirin.dialects import scf, ilist
from kirin.ir.method import Method
from kirin.passes.abc import Pass
from kirin.rewrite.abc import RewriteResult
from kirin.passes.inline import InlinePass

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

from .simplify_ifs import StimSimplifyIfs
from ..rewrite.ifs_to_stim import IfToStim


@dataclass
class AggressiveForLoopUnroll(Pass):
    """
    Aggressive unrolling of for loops, addresses cases where unroll
    does not successfully handle nested loops because of a lack of constprop.

    This should be invoked via fixpoint to let this be repeatedly applied until
    no further rewrites are possible.
    """

    def unsafe_run(self, mt: Method) -> RewriteResult:
        rule = Chain(
            InlineGetField(),
            InlineGetItem(),
            scf.unroll.ForLoop(),
            scf.trim.UnusedYield(),
        )

        # Intentionally only walk ONCE, let fixpoint happen with the WHOLE pass
        # so that HintConst gets run right after, allowing subsequent unrolls to happen
        rewrite_result = Walk(rule).rewrite(mt.code)

        rewrite_result = (
            HintConst(dialects=mt.dialects, no_raise=self.no_raise)
            .unsafe_run(mt)
            .join(rewrite_result)
        )

        return rewrite_result


@dataclass
class SquinToStimPass(Pass):

    def unsafe_run(self, mt: Method) -> RewriteResult:

        # inline aggressively:
        rewrite_result = InlinePass(
            dialects=mt.dialects, no_raise=self.no_raise
        ).unsafe_run(mt)

        rewrite_result = AggressiveForLoopUnroll(
            dialects=mt.dialects, no_raise=self.no_raise
        ).fixpoint(mt)

        rewrite_result = (
            Walk(Fixpoint(CFGCompactify())).rewrite(mt.code).join(rewrite_result)
        )
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
            CanonicalizeIList(dialects=mt.dialects, no_raise=self.no_raise)
            .unsafe_run(mt)
            .join(rewrite_result)
        )

        mt.print()

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
        rewrite_result = (
            Walk(
                IfToStim(
                    measure_analysis=meas_analysis_frame.entries,
                    measure_count=mia.measure_count,
                )
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
                    SquinWireToStim(),
                    SquinMeasureToStim(
                        measure_id_result=meas_analysis_frame.entries,
                        total_measure_count=mia.measure_count,
                    ),  # reduce duplicated logic, can split out even more rules later
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
