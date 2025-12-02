from dataclasses import dataclass

from kirin import ir
from kirin.passes import Fold, Pass, TypeInfer
from kirin.rewrite import Walk, Chain
from kirin.rewrite.abc import RewriteResult
from kirin.dialects.ilist.passes import IListDesugar

from bloqade import squin
from bloqade.squin.rewrite.qasm2 import (
    QASM2UOPToSquin,
    QASM2CoreToSquin,
    QASM2ExprToSquin,
)


@dataclass
class QASM2ToSquin(Pass):

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:

        # rewrite all QASM2 to squin first
        rewrite_result = Walk(
            Chain(
                QASM2ExprToSquin(),
                QASM2CoreToSquin(),
                QASM2UOPToSquin(),
            )
        ).rewrite(mt.code)

        # the rest is taken from the squin kernel

        rewrite_result = Fold(dialects=squin.kernel).fixpoint(mt)
        rewrite_result = (
            TypeInfer(dialects=squin.kernel).unsafe_run(mt).join(rewrite_result)
        )
        rewrite_result = (
            IListDesugar(dialects=squin.kernel).unsafe_run(mt).join(rewrite_result)
        )
        TypeInfer(dialects=squin.kernel).unsafe_run(mt).join(rewrite_result)

        return rewrite_result
