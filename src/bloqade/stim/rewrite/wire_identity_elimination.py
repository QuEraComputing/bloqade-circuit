from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin import wire


class SquinWireIdentityElimination(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """
        Handle the case where an unwrap feeds a wire directly into a wrap,
        equivalent to nothing happening/identity operation

        w = unwrap(qubit)
        wrap(qubit, w)
        """
        if isinstance(node, wire.Wrap):
            wire_origin_stmt = node.wire.owner
            if isinstance(wire_origin_stmt, wire.Unwrap):
                node.delete()  # get rid of wrap
                wire_origin_stmt.delete()  # get rid of the unwrap
                return RewriteResult(has_done_something=True)

        return RewriteResult()
