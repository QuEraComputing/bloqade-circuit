from dataclasses import dataclass

from kirin import ir
from kirin.dialects import py, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult


@dataclass
class FlattenAddOpIList(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, py.binop.Add):
            return RewriteResult()

        # check if we are adding two ilist.New objects
        if not (
            isinstance(node.lhs.owner, ilist.New)
            and isinstance(node.rhs.owner, ilist.New)
        ):
            return RewriteResult()

        new_stmt = ilist.New(values=node.lhs.owner.values + node.rhs.owner.values)
        node.replace_by(new_stmt)

        return RewriteResult(
            has_done_something=True,
        )
