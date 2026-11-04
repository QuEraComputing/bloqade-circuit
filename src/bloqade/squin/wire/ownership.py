"""Define function ownership conventions for explicit wire values."""

from kirin import ir

KEY = "squin.wire.owned"


def owns_inputs(method: ir.Method) -> bool:
    """Return whether the function consumes quantum inputs and returns every result explicitly."""
    return method.code.attributes.get(KEY) == ir.PyAttr(True)


def mark_owned(method: ir.Method) -> None:
    """Declare that quantum inputs transfer ownership into this function."""
    method.code.attributes[KEY] = ir.PyAttr(True)
