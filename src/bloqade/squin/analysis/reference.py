"""This module holds the reference analysis for squin kernels."""

from dataclasses import dataclass

from kirin import ir, types
from kirin.dialects import ilist

from bloqade import squin
from bloqade.types import QubitType
from bloqade.constants import constant_int
from bloqade.analysis.reference import (
    KEY,
    Whole,
    Register,
    Returned,
    ReferenceAnalysis,
)


@dataclass
class QubitReferenceAnalysis(ReferenceAnalysis):
    """A reference analysis whose roots are squin qubits and registers.

    `qubit.new` allocates a qubit root, and `squin.qalloc` allocates a register root.
    """

    keys = (KEY, "absint")

    def kind(self, type_: types.TypeAttribute) -> type[Whole] | type[Register] | None:
        """Return `Whole` for a qubit, `Register` for a list of qubits, else None."""
        if type_.is_subseteq(ilist.IListType[QubitType, types.Any]):
            return Register
        if type_.is_subseteq(QubitType):
            return Whole
        return None

    def register_length(self, root: ir.SSAValue, call: Returned | None) -> int | None:
        """Return the static length of the register root `root`, or None.

        A register that `squin.qalloc` returns has the constant size of the call,
        and a negative size allocates no qubit. A parameter has the length in its
        type.
        """
        if call is not None and call.callee is squin.qalloc:
            size = constant_int(call.call.args[0])
            return None if size is None else max(0, size)
        kind = root.type
        length = kind.vars[1] if isinstance(kind, types.Generic) else None
        if isinstance(length, types.Literal) and isinstance(length.data, int):
            return length.data
        return None
