"""Read constant values out of IR."""

from kirin import ir


def constant_int(value: ir.SSAValue) -> int | None:
    """Return the integer that the constant `value` holds, or None.

    The owner of `value` must carry the `ConstantLike` trait. A `bool` gives None.
    """
    owner = value.owner
    if not isinstance(owner, ir.Statement) or not owner.has_trait(ir.ConstantLike):
        return None
    attribute = owner.attributes.get("value")
    if not isinstance(attribute, ir.Data):
        return None
    data = attribute.unwrap()
    return data if isinstance(data, int) and not isinstance(data, bool) else None


def constant_float(value: ir.SSAValue) -> float | None:
    """Return the number that the constant `value` holds as a float, or None.

    An `int` constant gives its float value, and a `bool` gives None.
    """
    owner = value.owner
    if not isinstance(owner, ir.Statement) or not owner.has_trait(ir.ConstantLike):
        return None
    attribute = owner.attributes.get("value")
    if not isinstance(attribute, ir.Data):
        return None
    data = attribute.unwrap()
    if isinstance(data, bool) or not isinstance(data, (int, float)):
        return None
    return float(data)
