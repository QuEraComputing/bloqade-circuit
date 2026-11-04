"""Define which statements a complete wire conversion can keep.

The target keeps wire operations and classical operations whose values hold no qubit
references. A statement of a foreign dialect that holds no qubit reference also stays.
"""

from dataclasses import field, dataclass

from kirin import ir
from kirin.rewrite import Walk
from kirin.dialects import func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import qubit
from bloqade.squin import gate, noise
from bloqade.types import holds_qubits
from bloqade.squin.wire import stmts
from bloqade.native.dialects import gate as native_gate
from bloqade.squin.wire.group import (
    kernel as wire_kernel,
    is_wire,
    reference_kernel,
)

CLASSICAL_DIALECTS = reference_kernel.data - {
    qubit.dialect,
    gate.dialect,
    noise.dialect,
    native_gate.dialect,
}


@dataclass
class ConversionTarget(RewriteRule):
    """Collect the statements that violate the complete wire conversion target.

    Kirin's `Walk` visits every block and statement of the method, including those
    of nested regions. The rule records each violation and changes nothing.
    """

    violations: list[str] = field(default_factory=list)
    """The name of each violating statement, or "block argument"."""

    def rewrite_Block(self, node: ir.Block) -> RewriteResult:
        """Record a block argument that holds a qubit reference."""
        if any(holds_qubits(arg.type) for arg in node.args):
            self.violations.append("block argument")
        return RewriteResult()

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Record an operation that keeps references or lacks a supported wire form."""
        legal_dialect = (
            node.dialect in CLASSICAL_DIALECTS
            or node.dialect is stmts.dialect
            or node.dialect not in wire_kernel.data
            or isinstance(
                node, (qubit.stmts.IsZero, qubit.stmts.IsOne, qubit.stmts.IsLost)
            )
        )
        legal_values = not any(
            holds_qubits(value.type) for value in (*node.args, *node.results)
        )
        legal_call = not isinstance(node, func.Call) and (
            not isinstance(node, func.Invoke) or is_wire(node.callee)
        )
        legal_signature = not isinstance(node, func.Function) or not any(
            holds_qubits(kind)
            for kind in (*node.signature.inputs, node.signature.output)
        )
        if not (legal_dialect and legal_values and legal_call and legal_signature):
            self.violations.append(node.name)
        return RewriteResult()

    @classmethod
    def check(cls, method: ir.Method) -> list[str]:
        """Return every conversion violation in the method and its nested regions."""
        target = cls()
        Walk(target).rewrite(method.code)
        return target.violations
