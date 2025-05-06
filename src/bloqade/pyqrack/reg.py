import enum
from typing import TYPE_CHECKING
from dataclasses import dataclass

from bloqade.qasm2.types import Qubit

if TYPE_CHECKING:
    from pyqrack import QrackSimulator


class Measurement(enum.IntEnum):
    """Enumeration of measurement results."""

    Zero = 0
    One = 1
    Lost = enum.auto()


class CRegister(list[Measurement]):
    """Runtime representation of a classical register."""

    def __init__(self, size: int):
        super().__init__(Measurement.Zero for _ in range(size))


@dataclass(frozen=True)
class CBitRef:
    """Object representing a reference to a classical bit."""

    ref: CRegister
    """The classical register that is holding this bit."""

    pos: int
    """The position of this bit in the classical register."""

    def set_value(self, value: Measurement):
        self.ref[self.pos] = value

    def get_value(self):
        return self.ref[self.pos]


class QubitState(enum.Enum):
    Active = enum.auto()
    Lost = enum.auto()


@dataclass
class PyQrackQubit(Qubit):
    """The runtime representation of a qubit reference."""

    addr: int
    """The address of this qubit in the quantum register."""

    sim_reg: "QrackSimulator"
    """The register of the simulator."""

    state: QubitState
    """The state of the qubit (active/lost)"""

    def is_active(self) -> bool:
        """Check if the qubit is active.

        Returns
            True if the qubit is active, False otherwise.

        """
        return self.state is QubitState.Active

    def drop(self):
        """Drop the qubit in-place."""
        self.state = QubitState.Lost


@dataclass
class PyQrackWire:
    qubit: PyQrackQubit
