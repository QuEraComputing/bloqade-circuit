"""Describe the calling convention of converted wire functions.

A wire function returns the ordinary source results and then each in-out quantum
parameter, so `answer = f(q, n)` becomes `answer, q_next = f_wire(q, n)`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Sequence

from kirin import types
from kirin.dialects import func, ilist

from bloqade.types import QubitType, is_subtype, output_types
from bloqade.squin.wire.types import (
    WireType,
    RegisterType,
    register_type,
    literal_length,
)


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

    inout_positions: tuple[int, ...]
    """Hold the argument positions of the quantum parameters."""
    ordinary_count: int
    """Hold the number of ordinary source results."""
    packed: bool
    """State whether the source function returns 2 or more ordinary results as one tuple.

    A source tuple of one item stays one ordinary result of tuple type, so the wire
    function returns that tuple whole and keeps its shape.
    """

    @classmethod
    def of(cls, signature: func.Signature) -> Layout:
        """Read the layout from the signature of a source function."""
        ordinary_count = len(output_types(signature.output))
        inout_positions = tuple(
            i for i, typ in enumerate(signature.inputs) if quantum_type(typ) is not None
        )
        return cls(inout_positions, ordinary_count, ordinary_count > 1)

    def result_types(
        self, output: types.TypeAttribute
    ) -> tuple[types.TypeAttribute, ...]:
        """Return the type of each wire result for the wire output type `output`.

        A single wire result keeps its own type, even if that type is a tuple.
        """
        count = self.ordinary_count + len(self.inout_positions)
        outputs = (output,) if count == 1 else output_types(output)
        assert len(outputs) == count, f"{output} must have {count} wire results"
        return outputs


def quantum_type(typ: types.TypeAttribute) -> types.TypeAttribute | None:
    """Return the wire type of the squin type `typ`, or None for a classical type.

    A qubit becomes a wire, and a list of qubits at any depth becomes a register.
    """
    if is_subtype(typ, QubitType):
        return WireType
    if isinstance(typ, types.Generic) and is_subtype(typ, ilist.IListType):
        if quantum_type(typ.vars[0]) is not None:
            return RegisterType
    return None


def list_length(typ: types.TypeAttribute) -> int | None:
    """Return the static length of a list type, or None."""
    if isinstance(typ, types.Generic) and is_subtype(typ, ilist.IListType):
        return literal_length(typ.vars[1])
    return None


def register_shape(typ: types.TypeAttribute) -> tuple[int | None, ...]:
    """Return the source register dimensions in outer-to-inner order."""
    shape = []
    while isinstance(typ, types.Generic) and is_subtype(typ, ilist.IListType):
        shape.append(list_length(typ))
        typ = typ.vars[0]
    return tuple(shape)


def parameter_type(typ: types.TypeAttribute) -> types.TypeAttribute:
    """Return the wire type of a function parameter of the source type `typ`.

    A register keeps its number of qubits if the source type gives every
    dimension. For example, `IList[IList[Qubit, 2], 3]` becomes `Register[6]`.
    """
    linear = quantum_type(typ)
    if linear is None:
        return typ
    shape = register_shape(typ)
    if linear == RegisterType and shape and all(size is not None for size in shape):
        return register_type(math.prod(size for size in shape if size is not None))
    return linear
