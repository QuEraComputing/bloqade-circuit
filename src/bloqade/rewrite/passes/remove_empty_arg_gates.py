from dataclasses import dataclass

from kirin import ir, passes
from kirin.rewrite import Walk, Chain, Fixpoint, DeadCodeElimination
from kirin.rewrite.abc import RewriteResult

from bloqade.rewrite.rules.remove_empty_gates import (
    RemoveEmptyGate,
    RemoveEmptyGateCall,
)

from .callgraph import CallGraphPass


@dataclass
class RemoveEmptyArgGates(passes.Pass):
    """Remove squin gates, noise channels and measurements applied to empty qubit lists.

    A statement (or stdlib wrapper call) acting on a compile-time empty qubit list
    is a no-op and is removed. Dead code elimination then cleans up any functions
    and constants left unused.
    """

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        result = CallGraphPass(
            dialects=self.dialects,
            rule=Walk(Chain(RemoveEmptyGate(), RemoveEmptyGateCall())),
            no_raise=self.no_raise,
        ).unsafe_run(mt)

        result = Fixpoint(Walk(DeadCodeElimination())).rewrite(mt.code).join(result)
        return result
