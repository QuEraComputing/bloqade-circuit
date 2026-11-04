"""Describe the calling convention of converted wire functions.

A wire function returns the ordinary source results and then each borrowed quantum
parameter, so `answer = f(q, n)` becomes `answer, q_next = f_wire(q, n)`.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

from kirin import types
from kirin.dialects import func

from bloqade.types import is_subtype

from .types import quantum_type


def output_types(output: types.TypeAttribute) -> tuple[types.TypeAttribute, ...]:
    """Return the type of each output of a function whose output type is `output`.

    `None` gives no output. A tuple gives one output per member, and any other type
    gives one output.
    """
    if is_subtype(output, types.NoneType):
        return ()
    if isinstance(output, types.Generic) and is_subtype(output, types.Tuple):
        return tuple(output.vars)
    return (output,)


def packed_type(outputs: Sequence[types.TypeAttribute]) -> types.TypeAttribute:
    """Return the output type of a function with the output types `outputs`."""
    if not outputs:
        return types.NoneType
    if len(outputs) == 1:
        return outputs[0]
    return types.Generic(tuple, *outputs)


@dataclass(frozen=True)
class Layout:
    """Describe the wire results that the signature of a source function implies."""

    borrowed_positions: tuple[int, ...]
    """The argument positions of the quantum parameters."""
    ordinary_count: int
    """The number of ordinary source results."""
    packed: bool
    """Whether the source function returns 2 or more ordinary results as one tuple.

    A source tuple of one item stays one ordinary result of tuple type, so the wire
    function returns that tuple whole and keeps its shape.
    """

    @classmethod
    def of(cls, signature: func.Signature) -> Layout:
        """Read the layout from the signature of a source function."""
        ordinary_count = len(output_types(signature.output))
        borrowed_positions = tuple(
            i
            for i, kind in enumerate(signature.inputs)
            if quantum_type(kind) is not None
        )
        packed = (
            ordinary_count > 1
            and isinstance(signature.output, types.Generic)
            and is_subtype(signature.output, types.Tuple)
        )
        return cls(borrowed_positions, ordinary_count, packed)

    def result_types(
        self, output: types.TypeAttribute
    ) -> tuple[types.TypeAttribute, ...]:
        """Return the type of each wire result for the wire output type `output`.

        A single wire result keeps its own type, even if that type is a tuple.
        """
        count = self.ordinary_count + len(self.borrowed_positions)
        kinds = (output,) if count == 1 else output_types(output)
        if len(kinds) != count:
            raise ValueError(
                f"The wire output type {output} must have {count} results."
            )
        return kinds
