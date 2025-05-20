from dataclasses import dataclass

from kirin import ir
from kirin.passes import Pass
from kirin.rewrite import abc, walk
from kirin.dialects import py

from bloqade.qasm2 import types
from bloqade.qasm2.dialects import core


class IndexingDesugarRule(abc.RewriteRule):
    def rewrite_Statement(self, node: ir.Statement) -> abc.RewriteResult:
        if isinstance(node, py.indexing.GetItem):
            if node.obj.type.is_subseteq(types.QRegType):
                node.replace_by(core.QRegGet(reg=node.obj, idx=node.index))
                return abc.RewriteResult(has_done_something=True)
            elif node.obj.type.is_subseteq(types.CRegType):
                node.replace_by(core.CRegGet(reg=node.obj, idx=node.index))
                return abc.RewriteResult(has_done_something=True)

        return abc.RewriteResult()


@dataclass
class IndexingDesugarPass(Pass):
    def unsafe_run(self, mt: ir.Method) -> abc.RewriteResult:

        return walk.Walk(IndexingDesugarRule()).rewrite(mt.code)
