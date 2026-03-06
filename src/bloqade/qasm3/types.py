from kirin import types
from kirin.dialects import ilist

from bloqade.types import Qubit as Qubit, QubitType as QubitType


class Bit:
    """Runtime representation of a classical bit in QASM3."""

    pass


class BitReg:
    """Runtime representation of a classical bit register in QASM3."""

    def __getitem__(self, index) -> Bit:
        raise NotImplementedError("cannot call __getitem__ outside of a kernel")


QReg = ilist.IList[Qubit, types.Any]

BitType = types.PyClass(Bit)
"""Kirin type for a classical bit."""

QRegType = ilist.IListType[QubitType, types.Any]
"""Kirin type for a quantum register."""

BitRegType = types.PyClass(BitReg)
"""Kirin type for a classical bit register."""
