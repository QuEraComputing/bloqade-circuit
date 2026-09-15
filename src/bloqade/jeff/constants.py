"""Read constant values out of IR."""

from kirin import ir
from kirin.dialects import ilist


def _payload(value: ir.SSAValue) -> object:
    """Return the Python value that a constant holds, or None if `value` is no constant.

    If the constant holds an `IList`, the function returns the list inside the `IList`.
    """
    owner = value.owner
    if not isinstance(owner, ir.Statement) or not owner.has_trait(ir.ConstantLike):
        return None
    attribute = owner.attributes.get("value")
    if not isinstance(attribute, ir.Data):
        return None
    data = attribute.unwrap()
    return data.data if isinstance(data, ilist.IList) else data


def const_int(value: ir.SSAValue) -> int | None:
    """Return the integer that a constant value holds, or None.

    If the constant holds a `bool`, the function returns None.
    """
    data = _payload(value)
    if isinstance(data, int) and not isinstance(data, bool):
        return data
    return None
