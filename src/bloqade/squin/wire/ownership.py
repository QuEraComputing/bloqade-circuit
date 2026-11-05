"""Name the calling convention of a wire function.

An `InOut` function returns its ordinary results and then each quantum parameter in
its position. Jeff import marks each function that it converts as `Owns`, because a
Jeff function takes its qubits and returns every quantum result in its own order.
"""

from typing import TypeAlias
from dataclasses import dataclass
from collections.abc import Sequence

from kirin import ir, types
from kirin.dialects import func

from bloqade.types import output_types

from .types import is_linear

KEY = "squin.wire.owned"
"""Name the function attribute that marks an `Owns` function."""


@dataclass(frozen=True)
class InOut:
    """Name a function that returns each of its `count` quantum parameters last."""

    count: int


@dataclass(frozen=True)
class Owns:
    """Name a function that takes its quantum parameters and returns its qubits in any order."""


Convention: TypeAlias = InOut | Owns
"""Name the calling convention of a wire function."""


def convention(function: func.Function) -> Convention:
    """Return the calling convention of the wire function `function`."""
    if function.attributes.get(KEY) == ir.PyAttr(True):
        return Owns()
    return InOut(sum(is_linear(typ) for typ in function.signature.inputs))


def inout_result_type(
    function: func.Function,
    output: types.TypeAttribute,
    arguments: Sequence[types.TypeAttribute],
) -> types.TypeAttribute:
    """Refine the return suffix with the quantum argument types that the function preserves."""
    calling = convention(function)
    if (
        not isinstance(calling, InOut)
        or not calling.count
        or isinstance(output, types.BottomType)
    ):
        return output
    outputs = (output,) if is_linear(output) else output_types(output)
    if len(outputs) < calling.count:
        return output
    quantum = tuple(
        actual
        for actual, declared in zip(arguments, function.signature.inputs, strict=True)
        if is_linear(declared)
    )
    refined = (*outputs[: -calling.count], *quantum)
    return refined[0] if len(refined) == 1 else types.Generic(tuple, *refined)


def mark_owned(method: ir.Method) -> None:
    """Mark `method` as an `Owns` function."""
    method.code.attributes[KEY] = ir.PyAttr(True)


def clear_owned(method: ir.Method) -> None:
    """Remove the mark of `mark_owned`, so that `method` is an `InOut` function."""
    method.code.attributes.pop(KEY, None)
