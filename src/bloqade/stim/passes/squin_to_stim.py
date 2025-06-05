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

from bloqade.stim.groups import main as stim_main_group
from bloqade.stim.rewrite import (
    SquinWireToStim,
    PyConstantToStim,
    SquinQubitToStim,
    SquinMeasureToStim,
    SquinWireIdentityElimination,
)
from bloqade.squin.rewrite import RemoveDanglingQubits


@dataclass
class SquinToStim(Pass):

    def unsafe_run(self, mt: Method) -> RewriteResult:
        fold_pass = Fold(mt.dialects)
        # propagate constants
        rewrite_result = fold_pass(mt)

        # Assume that address analysis and
        # wrapping has been done before this pass!

        # Wrap Rewrite + SquinToStim can happen w/ standard walk
        rewrite_result = (
            Walk(
                Chain(
                    SquinQubitToStim(),
                    SquinWireToStim(),
                    SquinMeasureToStim(),  # reduce duplicated logic, can split out even more rules later
                    SquinWireIdentityElimination(),
                )
            )
            .rewrite(mt.code)
            .join(rewrite_result)
        )

        # Convert all PyConsts to Stim Constants
        rewrite_result = (
            Walk(Chain(PyConstantToStim())).rewrite(mt.code).join(rewrite_result)
        )

        # remove any squin.qubit.new that's left around
        ## Not considered pure so DCE won't touch it but
        ## it isn't being used anymore considering everything is a
        ## stim dialect statement
        rewrite_result = (
            Fixpoint(
                Walk(
                    Chain(
                        DeadCodeElimination(),
                        CommonSubexpressionElimination(),
                        RemoveDanglingQubits(),
                    )
                )
            )
            .rewrite(mt.code)
            .join(rewrite_result)
        )

        # do program verification here,
        # at this point the program should only have
        # stim dialect (and emission) supported statements.
        # Anything leftover from failed rewrites
        # (especially squin and scf!) will trigger an exception.
        mt_verification_clone = mt.similar(stim_main_group)
        print(mt_verification_clone.dialects)
        mt_verification_clone.verify()

        return rewrite_result
