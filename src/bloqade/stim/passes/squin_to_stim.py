from dataclasses import dataclass

from kirin.passes import Fold
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
    SquinWireToStim,
    SquinQubitToStim,
    SquinMeasureToStim,
    SquinWireIdentityElimination,
)
from bloqade.squin.rewrite import WrapAddressAnalysis
from bloqade.analysis.address import AddressAnalysis


@dataclass
class SquinToStim(Pass):

    def unsafe_run(self, mt: Method) -> RewriteResult:
        fold_pass = Fold(mt.dialects)
        # propagate constants
        rewrite_result = fold_pass(mt)

        # Get necessary analysis results to plug into hints
        address_analysis = AddressAnalysis(mt.dialects)
        address_frame, _ = address_analysis.run_analysis(mt)

        # Wrap Rewrite + SquinToStim can happen w/ standard walk
        rewrite_result = (
            Walk(
                Chain(
                    WrapAddressAnalysis(address_frame.entries),
                    SquinQubitToStim(),
                    SquinWireToStim(),
                    SquinMeasureToStim(),  # reduce duplicated logic, can split out even more rules later
                    SquinWireIdentityElimination(),
                )
            )
            .rewrite(mt.code)
            .join(rewrite_result)
        )

        rewrite_result = (
            Fixpoint(
                Walk(Chain(DeadCodeElimination(), CommonSubexpressionElimination()))
            )
            .rewrite(mt.code)
            .join(rewrite_result)
        )

        return rewrite_result
