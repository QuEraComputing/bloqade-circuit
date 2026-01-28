from dataclasses import dataclass

from kirin import ir
from kirin.passes import Fold, Pass, TypeInfer
from kirin.rewrite import Walk, Fixpoint, DeadCodeElimination
from kirin.rewrite.abc import RewriteResult

from bloqade.squin.rewrite.merge_U3 import RewriteMergeU3
from bloqade.squin.rewrite.non_clifford_to_U3 import RewriteNonCliffordToU3


@dataclass
class MergeSingleQubitGatesPass(Pass):
    """Merge consecutive single-qubit non-Clifford gates into a single U3.

    Pipeline:
    1) Rewrite non-Clifford 1q gates (T/Rx/Ry/Rz) to U3.
    2) Merge consecutive U3 gates (same qubit) to a single U3 until fixpoint.

    Note: merging currently only works when U3 parameters are compile-time
    constants (see RewriteMergeU3).
    """

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:

        # Step 1: make non-Clifford gates explicit U3.
        rewrite_result = Walk(RewriteNonCliffordToU3()).rewrite(mt.code)

        # Step 2: merge U3 runs until stable.
        rewrite_result = (
            Fixpoint(Walk(RewriteMergeU3())).rewrite(mt.code).join(rewrite_result)
        )

        # Clean up now-unused constants and keep IR sane for downstream passes.
        rewrite_result = (
            Fixpoint(Walk(DeadCodeElimination())).rewrite(mt.code).join(rewrite_result)
        )
        rewrite_result = Fold(dialects=mt.dialects).fixpoint(mt).join(rewrite_result)
        rewrite_result = (
            TypeInfer(dialects=mt.dialects).unsafe_run(mt).join(rewrite_result)
        )

        return rewrite_result
