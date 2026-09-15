"""This module holds the helper that splits a declared function output into values."""

from kirin import types

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
