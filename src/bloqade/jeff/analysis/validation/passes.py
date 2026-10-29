"""This module holds the validation passes for jeff IR."""

from kirin import ir
from kirin.lattice import EmptyLattice
from kirin.validation import ValidationPass
from kirin.analysis.forward import ForwardFrame

from bloqade.jeff.dialects import kernel

from .linearity import LinearityAnalysis
from .structure import StructureAnalysis


class StructureValidation(ValidationPass[ForwardFrame[EmptyLattice]]):
    """A validation pass that checks the statements, regions and types of functions."""

    def name(self) -> str:
        """Return the pass name that validation reports show."""
        return "jeff structure"

    def run(
        self, method: ir.Method
    ) -> tuple[ForwardFrame[EmptyLattice], list[ir.ValidationError]]:
        """Run the structure analysis and return its frame and validation errors."""
        analysis = StructureAnalysis(kernel)
        frame, _ = analysis.run(method)
        return frame, analysis.get_validation_errors()


class LinearityValidation(ValidationPass[ForwardFrame[EmptyLattice]]):
    """A validation pass that checks how each function uses wires and registers."""

    def name(self) -> str:
        """Return the pass name that validation reports show."""
        return "jeff linearity"

    def run(
        self, method: ir.Method
    ) -> tuple[ForwardFrame[EmptyLattice], list[ir.ValidationError]]:
        """Run the linearity analysis and return its frame and validation errors."""
        analysis = LinearityAnalysis(kernel)
        frame, _ = analysis.run(method)
        return frame, analysis.get_validation_errors()
