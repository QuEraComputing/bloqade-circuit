from dataclasses import dataclass

from kirin import ir
from kirin.rewrite import abc, dce, walk, fixpoint
from kirin.passes.abc import Pass

from ...dialects.noise.stmts import PauliChannel, CZPauliChannel, AtomLossChannel
from ...dialects.noise._dialect import dialect


class RemoveNoiseRewrite(abc.RewriteRule):
    def rewrite_Statement(self, node: ir.Statement) -> abc.RewriteResult:
        if isinstance(node, (AtomLossChannel, PauliChannel, CZPauliChannel)):
            node.delete()
            return abc.RewriteResult(has_done_something=True)

        return abc.RewriteResult()


@dataclass
class RemoveNoisePass(Pass):
    name = "remove-noise"

    def unsafe_run(self, mt: ir.Method) -> abc.RewriteResult:
        delete_walk = walk.Walk(RemoveNoiseRewrite())
        dce_walk = fixpoint.Fixpoint(walk.Walk(dce.DeadCodeElimination()))

        result = delete_walk.rewrite(mt.code)

        mt.dialects = ir.DialectGroup(mt.dialects.data.symmetric_difference([dialect]))

        if result.has_done_something:
            result = dce_walk.rewrite(mt.code)

        return result
