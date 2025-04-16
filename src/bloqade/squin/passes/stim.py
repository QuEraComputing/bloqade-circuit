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

import bloqade.squin.rewrite as squin_rewrite
from bloqade.analysis.address import AddressAnalysis
from bloqade.squin.analysis.nsites import (
    NSitesAnalysis,
)


@dataclass
class SquinToStim(Pass):

    def unsafe_run(self, mt: Method) -> RewriteResult:
        fold_pass = Fold(mt.dialects)
        # propagate constants
        rewrite_result = fold_pass(mt)

        # Get necessary analysis results to plug into hints
        address_analysis = AddressAnalysis(mt.dialects)
        address_frame, _ = address_analysis.run_analysis(mt)
        site_analysis = NSitesAnalysis(mt.dialects)
        sites_frame, _ = site_analysis.run_analysis(mt)

        # Wrap Rewrite + SquinToStim can happen w/ standard walk
        rewrite_result = (
            Walk(
                Chain(
                    squin_rewrite.WrapSquinAnalysis(
                        address_analysis=address_frame.entries,
                        op_site_analysis=sites_frame.entries,
                    ),
                    squin_rewrite._SquinToStim(),
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
