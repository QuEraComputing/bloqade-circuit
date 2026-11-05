"""Report the source statement and condition that prevent a wire conversion."""

from kirin import ir


class WireConversionError(ir.ValidationError):
    """Report the statement and the condition that prevent a wire conversion.

    The error is a Kirin `ValidationError`, so it records `node` and its source
    location. Its own class lets a caller tell a conversion failure from the other
    validation errors of Kirin.
    """

    def __init__(self, condition: str, node: ir.IRNode) -> None:
        """Record the failed condition at the statement `node`."""
        super().__init__(node, condition)

    def __str__(self) -> str:
        """Return the condition, followed by its source location if it is known."""
        condition = super().__str__()
        return condition if self.source is None else f"{condition}\n{self.source!r}"
