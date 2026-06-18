from dataclasses import field, dataclass

from kirin import ir, passes, rewrite
from kirin.rewrite import Walk, Fixpoint
from kirin.analysis import CallGraph
from kirin.rewrite.abc import RewriteResult

from bloqade.rewrite.passes.callgraph import ReplaceMethods
from bloqade.rewrite.rules.remove_empty_arg_gates import RemoveEmptyArgOps


@dataclass
class RemoveEmptyArgGates(passes.Pass):
    """Remove squin statements that act on compile-time-empty qubit lists."""

    fold_pass: passes.Fold = field(init=False)

    def __post_init__(self):
        """Initialize the fold pass used after rewrites."""
        self.fold_pass = passes.Fold(self.dialects, no_raise=self.no_raise)

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        """Remove empty-arg quantum ops across the method call graph."""
        result = RewriteResult()
        call_graph = CallGraph(mt)
        all_methods = set(call_graph.edges.keys()) | {mt}
        mt_map: dict[ir.Method, ir.Method] = {}

        for original_mt in all_methods:
            new_mt = original_mt if original_mt is mt else original_mt.similar()
            rule = Fixpoint(
                Walk(RemoveEmptyArgOps(call_graph=call_graph, callee=original_mt))
            )
            result = rule.rewrite(new_mt.code).join(result)
            mt_map[original_mt] = new_mt

        if result.has_done_something:
            for new_mt in mt_map.values():
                rewrite.Walk(ReplaceMethods(mt_map)).rewrite(new_mt.code)
                result = self.fold_pass(new_mt).join(result)

        return result
