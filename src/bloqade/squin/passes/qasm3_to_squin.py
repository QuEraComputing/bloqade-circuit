from dataclasses import dataclass

from kirin import ir
from kirin.passes import Fold, Pass, TypeInfer
from kirin.rewrite import Walk, Chain
from kirin.rewrite.abc import RewriteResult
from kirin.dialects.ilist.passes import IListDesugar

from bloqade import squin
from bloqade.squin.rewrite.qasm3 import (
    QASM3ExprToPy,
    QASM3DirectToSquin,
    QASM3ModifiedToSquin,
)

from .qasm3_gate_func_to_squin import QASM3GateFuncToSquinPass


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

        # rewrite all QASM3 to squin first
        rewrite_result = Walk(
            Chain(
                QASM3ExprToPy(),
                QASM3DirectToSquin(),
                QASM3ModifiedToSquin(),
            )
        ).rewrite(mt.code)

        # go into subkernels (custom gate bodies)
        rewrite_result = (
            QASM3GateFuncToSquinPass(dialects=mt.dialects)
            .unsafe_run(mt)
            .join(rewrite_result)
        )

        # kernel should be entirely in squin dialect now
        mt.dialects = squin.kernel

        # the rest is taken from the squin kernel
        rewrite_result = Fold(dialects=mt.dialects).fixpoint(mt)
        TypeInfer(dialects=mt.dialects).unsafe_run(mt)
        rewrite_result = (
            IListDesugar(dialects=mt.dialects).unsafe_run(mt).join(rewrite_result)
        )
        TypeInfer(dialects=mt.dialects).unsafe_run(mt)

        return rewrite_result
