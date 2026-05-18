from dataclasses import dataclass

from kirin import ir
from kirin.passes import Fold, Pass, TypeInfer
from kirin.rewrite import Walk, Chain
from kirin.rewrite.abc import RewriteResult
from kirin.dialects.ilist.passes import IListDesugar

from bloqade import squin
from bloqade.squin.rewrite.qasm2 import (
    QASM2IdToSquin,
    QASM2NoiseToSquin,
    QASM2DirectToSquin,
    QASM2ModifiedToSquin,
)

# There's a QASM2Py pass that only applies an _QASM2Py rewrite rule,
# I just want the rule here.
from bloqade.qasm2.passes.qasm2py import _QASM2Py as QASM2PyRule

from .qasm2_gate_func_to_squin import QASM2GateFuncToSquinPass


@dataclass
class QASM2ToSquin(Pass):
    """
    Converts a QASM2 kernel to a Squin kernel.

    Some gates like qasm2.U1 and U2 are rewritten to squin.u3 gate with the necessary
    additional values plugged in to maintain equivalence. The same goes for parallel.RZ and glob.UGate.
    For qasm2.noise gates, they are rewritten to equivalent squin.noise gates.

    Note that with the above, not all gates are convertible. For example, there is currently no support for
    converting a qasm2.CH or qasm2.Swap gate to squin due to the lack of a direct/near-direct equivalent.
    Furthermore, explicit classical register operations (e.g., `creg` and accessing/assigning elements from it)
    are not yet supported.
    """

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:

        # rewrite all QASM2 to squin first
        rewrite_result = Walk(
            Chain(
                QASM2PyRule(),
                QASM2NoiseToSquin(),
                QASM2IdToSquin(),
                QASM2DirectToSquin(),
                QASM2ModifiedToSquin(),
            )
        ).rewrite(mt.code)

        # go into subkernels
        rewrite_result = (
            QASM2GateFuncToSquinPass(dialects=mt.dialects)
            .unsafe_run(mt)
            .join(rewrite_result)
        )

        # kernel should be entirely in squin dialect now
        mt.dialects = squin.kernel

        # the rest is taken from the squin kernel
        rewrite_result = Fold(dialects=mt.dialects).fixpoint(mt)
        rewrite_result = (
            TypeInfer(dialects=mt.dialects).unsafe_run(mt).join(rewrite_result)
        ).join(rewrite_result)
        rewrite_result = (
            IListDesugar(dialects=mt.dialects).unsafe_run(mt).join(rewrite_result)
        ).join(rewrite_result)
        TypeInfer(dialects=mt.dialects).unsafe_run(mt).join(rewrite_result)

        return rewrite_result
