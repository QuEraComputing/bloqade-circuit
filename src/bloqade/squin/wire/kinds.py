"""Name the gates and noise channels of the wire dialect and state their arity.

A `Gate` or a `Noise` statement holds its kind as an attribute. The arity tables give
each kind its number of wires and parameters, which the statements check. A
measurement and a reset have one fixed arity each. `TRUNCATES` names the kinds whose
register form stops at the shortest register.
"""

import enum
from dataclasses import dataclass


class GateKind(enum.Enum):
    """Name each unitary gate of the wire dialect."""

    X = "x"
    Y = "y"
    Z = "z"
    H = "h"
    T = "t"
    S = "s"
    SQRT_X = "sqrt_x"
    SQRT_Y = "sqrt_y"
    RX = "rx"
    RY = "ry"
    RZ = "rz"
    CX = "cx"
    CY = "cy"
    CZ = "cz"
    CCZ = "ccz"
    SWAP = "swap"
    U3 = "u3"
    PHASED_XZ = "phased_x_z"
    NATIVE_CZ = "native_cz"
    NATIVE_R = "native_r"
    NATIVE_RZ = "native_rz"

    def __repr__(self) -> str:
        """Return the name, so that the IR prints `kind=cx`."""
        return self.value


class NoiseKind(enum.Enum):
    """Name each noise channel of the wire dialect."""

    SINGLE_QUBIT_PAULI_CHANNEL = "single_qubit_pauli_channel"
    TWO_QUBIT_PAULI_CHANNEL = "two_qubit_pauli_channel"
    DEPOLARIZE = "depolarize"
    DEPOLARIZE2 = "depolarize2"
    QUBIT_LOSS = "qubit_loss"
    QUBIT_LEAKAGE = "qubit_leakage"

    def __repr__(self) -> str:
        """Return the name, so that the IR prints `kind=depolarize`."""
        return self.value


@dataclass(frozen=True)
class Arity:
    """State the number of operands of one wire operation."""

    wires: int
    """The number of qubits that the operation acts on."""
    params: int = 0
    """The number of classical parameters, such as angles or probabilities."""


GATE_ARITY: dict[GateKind, Arity] = {
    GateKind.X: Arity(1),
    GateKind.Y: Arity(1),
    GateKind.Z: Arity(1),
    GateKind.H: Arity(1),
    GateKind.T: Arity(1),
    GateKind.S: Arity(1),
    GateKind.SQRT_X: Arity(1),
    GateKind.SQRT_Y: Arity(1),
    GateKind.RX: Arity(1, 1),
    GateKind.RY: Arity(1, 1),
    GateKind.RZ: Arity(1, 1),
    GateKind.CX: Arity(2),
    GateKind.CY: Arity(2),
    GateKind.CZ: Arity(2),
    GateKind.CCZ: Arity(3),
    GateKind.SWAP: Arity(2),
    GateKind.U3: Arity(1, 3),
    GateKind.PHASED_XZ: Arity(1, 3),
    GateKind.NATIVE_CZ: Arity(2),
    GateKind.NATIVE_R: Arity(1, 2),
    GateKind.NATIVE_RZ: Arity(1, 1),
}
"""Give the arity of each gate. Angles are in turns."""

NOISE_ARITY: dict[NoiseKind, Arity] = {
    NoiseKind.SINGLE_QUBIT_PAULI_CHANNEL: Arity(1, 3),
    NoiseKind.TWO_QUBIT_PAULI_CHANNEL: Arity(2, 1),
    NoiseKind.DEPOLARIZE: Arity(1, 1),
    NoiseKind.DEPOLARIZE2: Arity(2, 1),
    NoiseKind.QUBIT_LOSS: Arity(1, 1),
    NoiseKind.QUBIT_LEAKAGE: Arity(1, 2),
}
"""Give the arity of each noise channel."""

MEASURE_ARITY = Arity(1)
"""Give the arity of a measurement."""

RESET_ARITY = Arity(1)
"""Give the arity of a reset."""

TRUNCATES: frozenset[GateKind | NoiseKind] = frozenset(
    {
        GateKind.NATIVE_CZ,
        NoiseKind.TWO_QUBIT_PAULI_CHANNEL,
        NoiseKind.DEPOLARIZE2,
    }
)
"""Name the kinds whose register form stops at the shortest register.

The register form of every other kind needs registers of equal length.
"""
