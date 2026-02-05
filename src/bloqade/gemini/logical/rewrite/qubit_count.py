from dataclasses import dataclass

from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.ir.nodes.stmt import Statement

from ..dialects.operations.stmts import TerminalLogicalMeasurement


@dataclass
class InsertQubitCount(RewriteRule):
    num_physical_qubits: int

    def rewrite_Statement(self, node: Statement) -> RewriteResult:
        if not isinstance(node, TerminalLogicalMeasurement):
            return RewriteResult()

        node.num_physical_qubits = self.num_physical_qubits
        return RewriteResult(has_done_something=True)
