from dataclasses import dataclass

from kirin import ir
from kirin.passes import Fold, Pass, TypeInfer
from kirin.rewrite import Walk, Chain
from kirin.rewrite.abc import RewriteResult
from kirin.dialects.ilist.passes import IListDesugar

from bloqade import squin
from bloqade.squin.rewrite.qasm3 import (
    QASM3DirectToSquin,
    QASM3ModifiedToSquin,
)


@dataclass
class QASM3ToSquin(Pass):
    """
    Converts a QASM3 kernel to a Squin kernel.

    Maps all QASM3 gate, allocation, measurement, and reset statements
    to their squin equivalents using composable rewrite rules.
    Rotation gates (RX, RY, RZ) and UGate have their arguments reordered
    to match the squin calling convention.
    """

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        # Collect callees before rewriting so we can clean up backedges after.
        # QASM3ToSquin converts the method in-place to squin dialect, which
        # means the old qasm3 dialect-group passes stored in run_passes are
        # no longer valid.  If we leave the backedges intact, re-decorating a
        # callee gate (e.g. in a Jupyter notebook re-run) triggers
        # recompile_callers which tries to re-verify the now-squin IR with
        # the old qasm3 passes, causing a type error.
        callees: list[ir.Method] = []
        for stmt in mt.code.walk():
            trait = stmt.get_trait(ir.StaticCall)
            if trait:
                callees.append(trait.get_callee(stmt))

        rewrite_result = Walk(
            Chain(
                QASM3DirectToSquin(),
                QASM3ModifiedToSquin(),
            )
        ).rewrite(mt.code)

        mt.dialects = squin.kernel

        rewrite_result = Fold(dialects=mt.dialects).fixpoint(mt)
        rewrite_result = (
            TypeInfer(dialects=mt.dialects).unsafe_run(mt).join(rewrite_result)
        ).join(rewrite_result)
        rewrite_result = (
            IListDesugar(dialects=mt.dialects).unsafe_run(mt).join(rewrite_result)
        ).join(rewrite_result)
        TypeInfer(dialects=mt.dialects).unsafe_run(mt).join(rewrite_result)

        # Remove this method from callee backedges so that re-decorating a
        # callee gate won't attempt to recompile this (now squin) method
        # with the old qasm3 dialect-group passes.
        for callee in callees:
            callee.backedges.discard(mt)

        # Clear run_passes so that even if some other path triggers
        # recompilation, it won't run the stale qasm3 passes.
        mt.run_passes = None

        return rewrite_result
