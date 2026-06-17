from dataclasses import field, dataclass

from kirin import ir, passes
from kirin.rewrite import Walk, Chain, Inline, Fixpoint, DeadCodeElimination

from bloqade.rewrite.passes.callgraph import CallGraphPass
from bloqade.rewrite.rules.remove_empty_arg_gates import (
    QuantumOperation,
    RemoveEmptyArgOps,
)


@dataclass
class RemoveEmptyArgGates(passes.Pass):
    """Remove squin statements that act on compile-time-empty qubit lists."""

    callgraph_pass: CallGraphPass = field(init=False)

    def __post_init__(self):
        rule = Fixpoint(
            Walk(
                Chain(
                    Inline(
                        lambda code: sum(
                            1 for s in code.walk() if isinstance(s, QuantumOperation)
                        )
                        == 1
                    ),
                    RemoveEmptyArgOps(),
                    DeadCodeElimination(),
                )
            )
        )
        self.callgraph_pass = CallGraphPass(
            dialects=self.dialects, rule=rule, no_raise=self.no_raise
        )

    def unsafe_run(self, mt: ir.Method):
        return self.callgraph_pass.unsafe_run(mt)
