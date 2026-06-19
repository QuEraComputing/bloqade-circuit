from dataclasses import dataclass

from kirin import ir, passes
from kirin.rewrite import Walk
from kirin.rewrite.abc import RewriteResult

from bloqade.rewrite.passes.callgraph import CallGraphPass
from bloqade.rewrite.rules.remove_empty_arg_gates import RemoveEmptyArgOps


@dataclass
class RemoveEmptyArgGates(passes.Pass):
    """Remove squin statements that act on compile-time-empty qubit lists."""

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        """Remove empty-arg quantum ops across the method call graph."""
        return CallGraphPass(
            dialects=self.dialects,
            no_raise=self.no_raise,
            rule_factory=lambda callee, call_graph: Walk(
                RemoveEmptyArgOps(call_graph=call_graph, callee=callee)
            ),
        )(mt)
