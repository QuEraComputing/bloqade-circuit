from dataclasses import field, dataclass
from collections.abc import Callable

from kirin import ir, passes, rewrite
from kirin.analysis import CallGraph
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.dialects.func.stmts import Invoke


@dataclass
class ReplaceMethods(RewriteRule):
    new_symbols: dict[ir.Method, ir.Method]

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if (
            not isinstance(node, Invoke)
            or (new_callee := self.new_symbols.get(node.callee)) is None
        ):
            return RewriteResult()

        node.replace_by(
            Invoke(
                inputs=node.inputs,
                callee=new_callee,
                purity=node.purity,
            )
        )

        return RewriteResult(has_done_something=True)


@dataclass
class UpdateDialectsOnCallGraph(passes.Pass):
    """Update All dialects on the call graph to a new set of dialects given to this pass.

    Usage:
        pass_ = UpdateDialectsOnCallGraph(rule=rule, dialects=new_dialects)
        pass_(some_method)

    Note: This pass does not update the dialects of the input method, but copies
    all other methods invoked within it before updating their dialects.

    """

    fold_pass: passes.Fold = field(init=False)

    def __post_init__(self):
        self.fold_pass = passes.Fold(self.dialects, no_raise=self.no_raise)

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        mt_map = {}

        cg = CallGraph(mt)

        all_methods = set(sum(map(tuple, cg.defs.values()), ()))
        for original_mt in all_methods:
            if original_mt is mt:
                new_mt = original_mt
            else:
                new_mt = original_mt.similar(self.dialects)
            mt_map[original_mt] = new_mt

        result = RewriteResult()

        for _, new_mt in mt_map.items():
            result = (
                rewrite.Walk(ReplaceMethods(mt_map)).rewrite(new_mt.code).join(result)
            )
            self.fold_pass(new_mt)

        return result


@dataclass
class CallGraphPass(passes.Pass):
    """Copy all functions in the call graph and apply a rule to each of them.


    Usage:
        rule = Walk(SomeRewriteRule())
        pass_ = CallGraphPass(rule=rule, dialects=...)
        pass_(some_method)

        # or, when the rule needs per-method context:
        pass_ = CallGraphPass(
            rule_factory=lambda callee, call_graph: Walk(MyRule(callee, call_graph)),
            dialects=...,
        )

    Note: This pass modifies the input method in place, but copies
    all methods invoked within it before applying the rule to them.

    """

    rule: RewriteRule | None = None
    """The rule to apply to each function in the call graph."""

    rule_factory: Callable[[ir.Method, CallGraph], RewriteRule] | None = None
    """Build a per-method rule from the callee and call graph. Mutually exclusive with ``rule``."""

    fold_pass: passes.Fold = field(init=False)

    def __post_init__(self):
        if (self.rule is None) == (self.rule_factory is None):
            raise ValueError("CallGraphPass requires exactly one of rule or rule_factory")
        self.fold_pass = passes.Fold(self.dialects, no_raise=self.no_raise)

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        result = RewriteResult()
        mt_map = {}

        cg = CallGraph(mt)
        all_methods = set(cg.edges.keys())
        all_methods.add(mt)
        for original_mt in all_methods:
            if original_mt is mt:
                new_mt = original_mt
            else:
                new_mt = original_mt.similar()
            rule = (
                self.rule_factory(original_mt, cg)
                if self.rule_factory is not None
                else self.rule
            )
            result = rule.rewrite(new_mt.code).join(result)
            mt_map[original_mt] = new_mt

        if result.has_done_something:
            for _, new_mt in mt_map.items():
                rewrite.Walk(ReplaceMethods(mt_map)).rewrite(new_mt.code)
                self.fold_pass(new_mt)

        return result
