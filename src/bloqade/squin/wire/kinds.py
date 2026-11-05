"""Name the gates and noise channels of the wire dialect with their operand counts.

A `Gate` or a `Noise` statement holds its kind as an attribute. Each kind states how
many qubits and classical parameters it takes, which the statements check.
"""

import enum


class Kind(enum.Enum):
    """Hold the printed name and the operand counts of each member of a kind enum.

    If `truncates` is True, the register form of the kind stops at the shortest
    register. The register form of every other kind needs registers of equal length.
    """

    def __init__(
        self,
        label: str,
        qubit_count: int,
        param_count: int = 0,
        truncates: bool = False,
    ) -> None:
        """Record the name and the operand counts of the member."""
        self.label = label
        self.qubit_count = qubit_count
        self.param_count = param_count
        self.truncates = truncates

    def __repr__(self) -> str:
        """Return the name, so that the IR prints `kind=cx`."""
        return self.label


class GateKind(Kind):
    """Name each unitary gate of the wire dialect.

    A member holds its name, its number of qubits and its number of angles in turns.
    For example, `CX` takes 2 qubits, and `RZ` takes 1 qubit and 1 angle.
    """

    X = ("x", 1)
    Y = ("y", 1)
    Z = ("z", 1)
    H = ("h", 1)
    T = ("t", 1)
    S = ("s", 1)
    SQRT_X = ("sqrt_x", 1)
    SQRT_Y = ("sqrt_y", 1)
    RX = ("rx", 1, 1)
    RY = ("ry", 1, 1)
    RZ = ("rz", 1, 1)
    CX = ("cx", 2)
    CY = ("cy", 2)
    CZ = ("cz", 2)
    CCZ = ("ccz", 3)
    SWAP = ("swap", 2)
    U3 = ("u3", 1, 3)
    PHASED_XZ = ("phased_x_z", 1, 3)
    NATIVE_CZ = ("native_cz", 2, 0, True)
    NATIVE_R = ("native_r", 1, 2)
    NATIVE_RZ = ("native_rz", 1, 1)


class NoiseKind(Kind):
    """Name each noise channel of the wire dialect.

    A member holds its name, its number of qubits and its number of probabilities.
    """

    SINGLE_QUBIT_PAULI_CHANNEL = ("single_qubit_pauli_channel", 1, 3)
    TWO_QUBIT_PAULI_CHANNEL = ("two_qubit_pauli_channel", 2, 1, True)
    DEPOLARIZE = ("depolarize", 1, 1)
    DEPOLARIZE2 = ("depolarize2", 2, 1, True)
    QUBIT_LOSS = ("qubit_loss", 1, 1)
    QUBIT_LEAKAGE = ("qubit_leakage", 1, 2)
