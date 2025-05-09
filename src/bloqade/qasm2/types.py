from typing import Any, TypeAlias

from kirin import types
from kirin.dialects import ilist

from bloqade.types import Qubit as Qubit, QubitType as QubitType


class Bit:
    """Runtime representation of a bit.

    Note:
        This is the base class of more specific bit types, such as
        a reference to a piece of classical register in some quantum register
        dialects.
    """

    pass


QReg: TypeAlias = ilist.IList[Qubit, Any]


class CReg:
    """Runtime representation of a classical register."""

    def __getitem__(self, index) -> Bit:
        raise NotImplementedError("cannot call __getitem__ outside of a kernel")


BitType = types.PyClass(Bit)
"""Kirin type for a classical bit."""

N = types.TypeVar("N")
QRegType = ilist.IListType[QubitType, N]
"""Kirin type for a quantum register."""

CRegType = types.PyClass(CReg)
"""Kirin type for a classical register."""
