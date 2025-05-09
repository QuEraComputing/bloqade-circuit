from dataclasses import dataclass

from kirin import ir
from kirin.passes import Pass
from kirin.rewrite import Walk, Chain, abc

from bloqade.qasm2.dialects import core


class MeasureDesugarRule(abc.RewriteRule):
    def rewrite_Statement(self, node: ir.Statement) -> abc.RewriteResult:
        if isinstance(node, core.MeasureAny):
            if node.qarg.type.is_subseteq(core.QRegType):
                node.replace_by(core.MeasureQReg(qarg=node.qarg, carg=node.carg))
                return abc.RewriteResult(has_done_something=True)
            elif node.qarg.type.is_subseteq(core.QubitType):
                node.replace_by(core.MeasureQubit(qarg=node.qarg, carg=node.carg))
                return abc.RewriteResult(has_done_something=True)

        return abc.RewriteResult()


@dataclass
class QASMDesugarPass(Pass):
    def unsafe_run(self, mt: ir.Method) -> abc.RewriteResult:
        return Walk(Chain(MeasureDesugarRule())).rewrite(mt.code)
