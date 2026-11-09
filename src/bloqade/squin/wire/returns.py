"""Define how wire functions return their quantum arguments.

`PreserveArguments` returns classical results followed by the updated quantum
arguments in their original order. `ExplicitReturns` keeps all declared results
and allows quantum values to change positions across returns, loops and branches.
Both policies require valid wire consumption and register borrowing.
"""

from enum import Enum
from typing import cast
from collections.abc import Sequence

from kirin import ir, types
from kirin.dialects import func

from bloqade.types import output_types

from .types import is_linear

KEY = "squin.wire.return_policy"
"""Name the function attribute that stores its return policy."""


class ReturnPolicy(Enum):
    """Specify how validation and conversion interpret quantum return values."""

    PreserveArguments = "preserve_arguments"
    ExplicitReturns = "explicit_returns"


def return_policy(function: func.Function) -> ReturnPolicy:
    """Return the function's policy, which defaults to preserving quantum arguments."""
    attribute = function.attributes.get(KEY)
    if attribute is None:
        return ReturnPolicy.PreserveArguments
    return cast(ir.PyAttr[ReturnPolicy], attribute).data


def set_return_policy(method: ir.Method, policy: ReturnPolicy) -> None:
    """Set the return policy of the wire method."""
    method.code.attributes[KEY] = ir.PyAttr(policy)


def quantum_parameter_count(signature: func.Signature) -> int:
    """Count the wire and register parameters in the function signature."""
    return sum(is_linear(typ) for typ in signature.inputs)


def preserved_result_type(
    function: func.Function,
    output: types.TypeAttribute,
    arguments: Sequence[types.TypeAttribute],
) -> types.TypeAttribute:
    """Refine the return suffix with the quantum argument types that the function preserves."""
    count = quantum_parameter_count(function.signature)
    if (
        return_policy(function) is ReturnPolicy.ExplicitReturns
        or not count
        or isinstance(output, types.BottomType)
    ):
        return output
    outputs = (output,) if is_linear(output) else output_types(output)
    if len(outputs) < count:
        return output
    quantum = tuple(
        actual
        for actual, declared in zip(arguments, function.signature.inputs, strict=True)
        if is_linear(declared)
    )
    refined = (*outputs[:-count], *quantum)
    return refined[0] if len(refined) == 1 else types.Generic(tuple, *refined)
