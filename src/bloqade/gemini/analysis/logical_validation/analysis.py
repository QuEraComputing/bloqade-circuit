from typing import Any
from dataclasses import dataclass

from kirin import ir
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward, ForwardFrame
from kirin.validation import ValidationPass

from bloqade import squin


class _GeminiLogicalValidationAnalysis(Forward[EmptyLattice]):
    keys = ["gemini.validate.logical"]

    first_gate = True
    lattice = EmptyLattice

    def eval_fallback(self, frame: ForwardFrame, node: ir.Statement):
        if isinstance(node, squin.gate.stmts.Gate):
            # NOTE: to validate that only the first encountered gate can be non-Clifford, we need to track this here
            self.first_gate = False

        return tuple(self.lattice.bottom() for _ in range(len(node.results)))

    def method_self(self, method: ir.Method) -> EmptyLattice:
        return self.lattice.bottom()


@dataclass
class GeminiLogicalValidation(ValidationPass):
    """Validates a logical gemini program"""

    _analysis: _GeminiLogicalValidationAnalysis | None = None

    def name(self) -> str:
        return "Gemini Logical Validation"

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        analysis = _GeminiLogicalValidationAnalysis(method.dialects)
        frame, _ = analysis.run(method)

        return frame, analysis.get_validation_errors()
