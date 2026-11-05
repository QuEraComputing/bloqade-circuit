"""Check squin conversion with the same wire pipeline that emits Jeff."""

from kirin import ir
from kirin.validation import ValidationPass
from kirin.ir.exception import ValidationErrorGroup


class SquinToJeffValidation(ValidationPass[ir.Method | None]):
    """Report the actual conversion errors while preserving the input method."""

    def name(self) -> str:
        """Return the pass name for conversion diagnostics."""
        return "SquinToJeff"

    def run(
        self, method: ir.Method
    ) -> tuple[ir.Method | None, list[ir.ValidationError]]:
        """Convert a private copy and return its Jeff method or validation errors."""
        from bloqade.jeff.squin2jeff.pipeline import SquinToJeff

        try:
            return SquinToJeff().emit(method), []
        except ValidationErrorGroup as error:
            return None, [ir.ValidationError(method.code, str(error))]
