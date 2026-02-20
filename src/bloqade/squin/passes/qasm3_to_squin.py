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

        return rewrite_result
