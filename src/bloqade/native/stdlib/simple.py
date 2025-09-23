from kirin.dialects import ilist

from bloqade.squin import qubit

from . import broadcast
from .._prelude import kernel


@kernel
def rx(angle: float, qubit: qubit.Qubit):
    """Single qubit X-rotation by angle (in radians).

    Args:
        angle (float): Rotation angle in radians.
        qubit (qubit.Qubit): The qubit to apply the rotation to.

    """
    broadcast.rx(angle, ilist.IList([qubit]))


@kernel
def x(qubit: qubit.Qubit):
    """X gate (NOT gate) on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the X gate to.

    """
    broadcast.x(ilist.IList([qubit]))


@kernel
def sqrt_x(qubit: qubit.Qubit):
    """Square root of X gate on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the sqrt(X) gate to.

    """
    broadcast.sqrt_x(ilist.IList([qubit]))


@kernel
def sqrt_x_adj(qubit: qubit.Qubit):
    """Adjoint of the square root of X gate on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the adjoint sqrt(X) gate to.
    """
    broadcast.sqrt_x_adj(ilist.IList([qubit]))


@kernel
def ry(angle: float, qubit: qubit.Qubit):
    """Rotation around the Y axis by angle (in radians).

    Args:
        angle (float): Rotation angle in radians.
        qubit (qubit.Qubit): The qubit to apply the rotation to.

    """
    broadcast.ry(angle, ilist.IList([qubit]))


@kernel
def y(qubit: qubit.Qubit):
    """Y gate (also known as the Pauli-Y gate) on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the Y gate to.

    """
    broadcast.y(ilist.IList([qubit]))


@kernel
def sqrt_y(qubit: qubit.Qubit):
    """Square root of Y gate on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the sqrt(Y) gate to.

    """
    broadcast.sqrt_y(ilist.IList([qubit]))


@kernel
def sqrt_y_adj(qubit: qubit.Qubit):
    """Adjoint of the square root of Y gate on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the adjoint sqrt(Y) gate to.
    """
    broadcast.sqrt_y_adj(ilist.IList([qubit]))


@kernel
def rz(angle: float, qubit: qubit.Qubit):
    """Rotation around the Z axis by angle (in radians).

    Args:
        angle (float): Rotation angle in radians.
        qubit (qubit.Qubit): The qubit to apply the rotation to.
    """
    broadcast.rz(angle, ilist.IList([qubit]))


@kernel
def z(qubit: qubit.Qubit):
    """Z gate (also known as the Pauli-Z gate) on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the Z gate to.
    """
    broadcast.z(ilist.IList([qubit]))


@kernel
def s(qubit: qubit.Qubit):
    """S gate (also known as the Phase gate) on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the S gate to.
    """
    broadcast.s(ilist.IList([qubit]))


@kernel
def s_dag(qubit: qubit.Qubit):
    """Adjoint of the S gate (also known as the Phase gate) on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the adjoint S gate to.
    """
    broadcast.s_adj(ilist.IList([qubit]))


@kernel
def h(qubit: qubit.Qubit):
    """Hadamard gate on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the Hadamard gate to.
    """
    broadcast.h(ilist.IList([qubit]))


@kernel
def t(qubit: qubit.Qubit):
    """T gate (also known as the Phase gate) on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the T gate to.
    """
    broadcast.t(ilist.IList([qubit]))


@kernel
def shift(angle: float, qubit: qubit.Qubit):
    """Shift gate on a single qubit.

    Args:
        angle (float): Shift angle in radians.
        qubit (qubit.Qubit): The qubit to apply the Shift gate to.

    """
    broadcast.shift(angle, ilist.IList([qubit]))


@kernel
def rot(phi: float, theta: float, omega: float, qubit: qubit.Qubit):
    """3-axis rotation gate on a single qubit.

    Args:
        phi (float): Rotation angle around the Z axis in radians.
        theta (float): Rotation angle around the Y axis in radians.
        omega (float): Rotation angle around the Z axis in radians.
        qubit (qubit.Qubit): The qubit to apply the rotation to.

    """
    broadcast.rot(phi, theta, omega, ilist.IList([qubit]))


@kernel
def u3(theta: float, phi: float, lam: float, qubit: qubit.Qubit):
    """U3 gate on a single qubit.

    Args:
        theta (float): Rotation angle around the Y axis in radians.
        phi (float): Rotation angle around the Z axis in radians.
        lam (float): Rotation angle around the Z axis in radians.
        qubit (qubit.Qubit): The qubit to apply the U3 gate to

    """
    broadcast.u3(theta, phi, lam, ilist.IList([qubit]))


@kernel
def cz(control: qubit.Qubit, target: qubit.Qubit):
    """Controlled-Z gate on two qubits.

    Args:
        control (qubit.Qubit): The control qubit.
        target (qubit.Qubit): The target qubit.
    """
    broadcast.cz(ilist.IList([control]), ilist.IList([target]))


@kernel
def cx(control: qubit.Qubit, target: qubit.Qubit):
    """Controlled-X gate on two qubits.

    Args:
        control (qubit.Qubit): the control qubit.
        target (qubit.Qubit): the target qubit.
    """
    broadcast.cx(ilist.IList([control]), ilist.IList([target]))


@kernel
def cy(control: qubit.Qubit, targets: qubit.Qubit):
    """Controlled-Y gate on two qubits.

    Args:
        control (qubit.Qubit): the control qubit.
        targets (qubit.Qubit): the target qubit.
    """
    broadcast.cy(ilist.IList([control]), ilist.IList([targets]))


__all__ = [
    "x",
    "y",
    "z",
    "s",
    "h",
    "t",
    "s_dag",
    "sqrt_x",
    "sqrt_x_adj",
    "sqrt_y",
    "sqrt_y_adj",
    "rx",
    "ry",
    "rz",
    "cz",
    "cx",
    "cy",
    "shift",
    "rot",
    "u3",
]
