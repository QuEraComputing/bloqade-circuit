"""Define which statements a complete wire conversion can keep.

The target keeps wire operations and classical operations whose values hold no qubit
references. A statement of a foreign dialect that holds no qubit reference also stays.
"""

from dataclasses import field, dataclass

from kirin import ir
from kirin.rewrite import Walk
from kirin.dialects import func
from kirin.validation import ValidationPass
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import qubit
from bloqade.squin import gate, noise
from bloqade.types import holds_qubits
from bloqade.native.dialects import gate as native_gate
from bloqade.squin.wire.group import (
    WIRE_DIALECTS,
    kernel as wire_kernel,
    is_wire,
    reference_kernel,
)

CLASSICAL_DIALECTS: frozenset[ir.Dialect] = reference_kernel.data - {
    qubit.dialect,
    gate.dialect,
    noise.dialect,
    native_gate.dialect,
}
"""Name the dialects of the reference kernel that hold only classical statements."""


@dataclass
class TargetViolations(RewriteRule):
    """Collect the statements and blocks that violate the wire conversion target.

    Kirin's `Walk` visits every block and statement of the method, including those
    of nested regions. The rule records each violation and changes nothing.
    """

    errors: list[ir.ValidationError] = field(default_factory=list)
    """Hold one error for each violating statement or block."""

    def rewrite_Block(self, node: ir.Block) -> RewriteResult:
        """Record a block argument that holds a qubit reference."""
        if any(holds_qubits(arg.type) for arg in node.args):
            self.errors.append(
                ir.ValidationError(node, "A block argument holds a qubit reference.")
            )
        return RewriteResult()

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Record an operation that keeps references or lacks a supported wire form."""
        legal_dialect = (
            node.dialect in CLASSICAL_DIALECTS
            or node.dialect in WIRE_DIALECTS
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
            holds_qubits(typ) for typ in (*node.signature.inputs, node.signature.output)
        )
        if not (legal_dialect and legal_values and legal_call and legal_signature):
            self.errors.append(
                ir.ValidationError(
                    node, f"'{node.name}' violates the wire conversion target."
                )
            )
        return RewriteResult()


class ConversionTarget(ValidationPass[None]):
    """Check that a conversion left only wire and classical operations."""

    def name(self) -> str:
        """Return the pass name that validation reports show."""
        return "squin wire target"

    def run(self, method: ir.Method) -> tuple[None, list[ir.ValidationError]]:
        """Return one error for each statement or block outside the target."""
        violations = TargetViolations()
        Walk(violations).rewrite(method.code)
        return None, violations.errors

    @classmethod
    def check(cls, method: ir.Method) -> list[str]:
        """Return the name of each violating statement, or "block argument"."""
        _, errors = cls().run(method)
        return [
            (
                error.node.name
                if isinstance(error.node, ir.Statement)
                else "block argument"
            )
            for error in errors
        ]
