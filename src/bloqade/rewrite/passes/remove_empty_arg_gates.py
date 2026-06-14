from dataclasses import field, dataclass
from kirin import ir, passes
from kirin.rewrite import Walk, Chain, DeadCodeElimination
from .callgraph import CallGraphPass
from ..rules.remove_empty_arg_gates import RemoveEmptyArgGatesRule

@dataclass
class RemoveEmptyArgGates(passes.Pass):
    def unsafe_run(self, mt: ir.Method):
        # We walk the call graph and apply the removal rule followed by DCE 
        # to clean up any leftover definitions or empty functions.
        rule = Walk(Chain(RemoveEmptyArgGatesRule(), DeadCodeElimination()))
        cg_pass = CallGraphPass(dialects=self.dialects, rule=rule)
        return cg_pass(mt)
