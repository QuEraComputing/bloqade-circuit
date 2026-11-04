"""Check wire squin with the kirin validation suite `WireValidation`.

The suite checks structure and types, single use, borrowed elements and qubit positions.
"""

from dataclasses import replace, dataclass

from kirin import ir
from kirin.validation import ValidationPass, ValidationSuite

from bloqade.squin.analysis.validation.wire.borrows import BorrowValidation
from bloqade.squin.analysis.validation.wire.position import PositionValidation
from bloqade.squin.analysis.validation.wire.linearity import LinearityValidation


class StructureValidation(ValidationPass[None]):
    """Run kirin's own structure and type checks on a method.

    `WireValidation` runs this check on wire methods, and `SquinToWire` runs it on
    source methods.
    """

    def name(self) -> str:
        """Return the pass name that validation reports show."""
        return "squin wire structure"

    def run(self, method: ir.Method) -> tuple[None, list[ir.ValidationError]]:
        """Return the error of `verify` or `verify_type`, if either check fails."""
        try:
            method.code.verify()
            method.code.verify_type()
        except ir.ValidationError as error:
            error.source = None if error.source is None else replace(error.source)
            return None, [error]
        return None, []


@dataclass
class WireValidation:
    """Run the wire structure, linearity, borrow and position checks."""

    def check(self, method: ir.Method) -> None:
        """Raise a `ValidationErrorGroup` that lists every broken rule of `method`."""
        suite = ValidationSuite(
            [
                StructureValidation,
                LinearityValidation,
                BorrowValidation,
                PositionValidation,
            ]
        )
        suite.validate(method).raise_if_invalid()
