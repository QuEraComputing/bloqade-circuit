from kirin.lowering import wraps

from .types import Bit, QReg, Qubit, BitReg
from .dialects import uop, core, expr


@wraps(core.QRegNew)
def qreg(n_qubits: int) -> QReg:
    """Create a new quantum register.

    Args:
        n_qubits: The number of qubits in the register.
    """
    ...


@wraps(core.BitRegNew)
def bitreg(n_bits: int) -> BitReg:
    """Create a new classical bit register.

    Args:
        n_bits: The number of bits in the register.
    """
    ...


@wraps(core.Reset)
def reset(qarg: Qubit) -> None:
    """Reset the qubit to the |0> state.

    Args:
        qarg: The qubit to reset.
    """
    ...


@wraps(core.Measure)
def measure(qarg: Qubit, carg: Bit) -> None:
    """Measure a qubit and store the result in a classical bit.

    Args:
        qarg: The qubit to measure.
        carg: The classical bit to store the result in.
    """
    ...


# Single-qubit gates


@wraps(uop.H)
def h(qarg: Qubit) -> None:
    """Apply the Hadamard gate.

    Args:
        qarg: The qubit to apply the gate to.
    """
    ...


@wraps(uop.X)
def x(qarg: Qubit) -> None:
    """Apply the X (Pauli-X) gate.

    Args:
        qarg: The qubit to apply the gate to.
    """
    ...


@wraps(uop.Y)
def y(qarg: Qubit) -> None:
    """Apply the Y (Pauli-Y) gate.

    Args:
        qarg: The qubit to apply the gate to.
    """
    ...


@wraps(uop.Z)
def z(qarg: Qubit) -> None:
    """Apply the Z (Pauli-Z) gate.

    Args:
        qarg: The qubit to apply the gate to.
    """
    ...


@wraps(uop.S)
def s(qarg: Qubit) -> None:
    """Apply the S gate.

    Args:
        qarg: The qubit to apply the gate to.
    """
    ...


@wraps(uop.T)
def t(qarg: Qubit) -> None:
    """Apply the T gate.

    Args:
        qarg: The qubit to apply the gate to.
    """
    ...


# Rotation gates


@wraps(uop.RX)
def rx(qarg: Qubit, theta: float) -> None:
    """Apply the RX rotation gate.

    Args:
        qarg: The qubit to apply the gate to.
        theta: The rotation angle.
    """
    ...


@wraps(uop.RY)
def ry(qarg: Qubit, theta: float) -> None:
    """Apply the RY rotation gate.

    Args:
        qarg: The qubit to apply the gate to.
        theta: The rotation angle.
    """
    ...


@wraps(uop.RZ)
def rz(qarg: Qubit, theta: float) -> None:
    """Apply the RZ rotation gate.

    Args:
        qarg: The qubit to apply the gate to.
        theta: The rotation angle.
    """
    ...


# Two-qubit controlled gates


@wraps(uop.CX)
def cx(ctrl: Qubit, qarg: Qubit) -> None:
    """Apply the CNOT (CX) gate.

    Args:
        ctrl: The control qubit.
        qarg: The target qubit.
    """
    ...


@wraps(uop.CY)
def cy(ctrl: Qubit, qarg: Qubit) -> None:
    """Apply the Controlled-Y gate.

    Args:
        ctrl: The control qubit.
        qarg: The target qubit.
    """
    ...


@wraps(uop.CZ)
def cz(ctrl: Qubit, qarg: Qubit) -> None:
    """Apply the Controlled-Z gate.

    Args:
        ctrl: The control qubit.
        qarg: The target qubit.
    """
    ...


# General unitary gate


@wraps(uop.UGate)
def u(qarg: Qubit, theta: float, phi: float, lam: float) -> None:
    """Apply a general single-qubit unitary U(theta, phi, lam).

    Args:
        qarg: The qubit to apply the gate to.
        theta: The theta parameter.
        phi: The phi parameter.
        lam: The lambda parameter.
    """
    ...


@wraps(core.Barrier)
def barrier(*qargs: Qubit) -> None:
    """Barrier synchronization across a set of qubits.

    Args:
        qargs: The qubits to synchronize.
    """
    ...


# Arithmetic helpers


@wraps(expr.ConstPI)
def pi() -> float:
    """Return the constant PI."""
    ...
