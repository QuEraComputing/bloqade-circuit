"""This module holds helpers that match returned values to a declared output."""

from collections.abc import Sequence

from kirin import ir, types

from bloqade.jeff.types import is_subtype


def declared_outputs(output: types.TypeAttribute) -> tuple[types.TypeAttribute, ...]:
    """Return a declared function output as one type per output value.

    For example, `tuple[Wire, bool]` gives `(Wire, bool)` and `None` gives `()`.
    """
    if is_subtype(output, types.NoneType):
        return ()
    if isinstance(output, types.Generic) and is_subtype(output, types.Tuple):
        return tuple(output.vars)
    return (output,)


def output_type(values: Sequence[ir.SSAValue]) -> types.TypeAttribute:
    """Return the output type for returned values: none, one, or a tuple."""
    if not values:
        return types.NoneType
    if len(values) == 1:
        return values[0].type
    return types.Generic(tuple, *(value.type for value in values))
