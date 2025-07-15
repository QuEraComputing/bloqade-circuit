from dataclasses import dataclass

from kirin import ir
from kirin.analysis import const
from kirin.dialects import py, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult


@dataclass
class InlineGetItemFromIList(RewriteRule):
    constprop_result: dict[ir.SSAValue, const.Result]

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, py.indexing.GetItem):
            return RewriteResult()

        if not isinstance(node.obj.owner, ilist.New):
            return RewriteResult()

        if not isinstance(
            index_value := self.constprop_result.get(node.index), const.Value
        ):
            return RewriteResult()

        elem_ssa = node.obj.owner.values[index_value.data]

        node.result.replace_by(elem_ssa)

        return RewriteResult(
            has_done_something=True,
        )
