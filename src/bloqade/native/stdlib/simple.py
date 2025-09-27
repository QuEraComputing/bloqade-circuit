from kirin.dialects import ilist

from bloqade.squin import qubit

from . import broadcast
from .._prelude import kernel


@kernel
def rx(angle: float, qubit: qubit.Qubit):
    """Apply an RX rotation gate on a single qubit.

    Args:
        angle (float): Rotation angle in radians.
        qubit (qubit.Qubit): The qubit to apply the rotation to.
    """
    broadcast.rx(angle, ilist.IList([qubit]))


@kernel
def x(qubit: qubit.Qubit):
    """Apply a Pauli-X gate on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the X gate to.
    """
    broadcast.x(ilist.IList([qubit]))


@kernel
def sqrt_x(qubit: qubit.Qubit):
    """Apply a sqrt(X) gate on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the sqrt(X) gate to.
    """
    broadcast.sqrt_x(ilist.IList([qubit]))


@kernel
def sqrt_x_adj(qubit: qubit.Qubit):
    """Apply the adjoint of sqrt(X) on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the adjoint sqrt(X) gate to.
    """
    broadcast.sqrt_x_adj(ilist.IList([qubit]))


@kernel
def ry(angle: float, qubit: qubit.Qubit):
    """Apply an RY rotation gate on a single qubit.

    Args:
        angle (float): Rotation angle in radians.
        qubit (qubit.Qubit): The qubit to apply the rotation to.
    """
    broadcast.ry(angle, ilist.IList([qubit]))


@kernel
def y(qubit: qubit.Qubit):
    """Apply a Pauli-Y gate on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the Y gate to.
    """
    broadcast.y(ilist.IList([qubit]))


@kernel
def sqrt_y(qubit: qubit.Qubit):
    """Apply a sqrt(Y) gate on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the sqrt(Y) gate to.
    """
    broadcast.sqrt_y(ilist.IList([qubit]))


@kernel
def sqrt_y_adj(qubit: qubit.Qubit):
    """Apply the adjoint of sqrt(Y) on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the adjoint sqrt(Y) gate to.
    """
    broadcast.sqrt_y_adj(ilist.IList([qubit]))


@kernel
def rz(angle: float, qubit: qubit.Qubit):
    """Apply an RZ rotation gate on a single qubit.

    Args:
        angle (float): Rotation angle in radians.
        qubit (qubit.Qubit): The qubit to apply the rotation to.
    """
    broadcast.rz(angle, ilist.IList([qubit]))


@kernel
def z(qubit: qubit.Qubit):
    """Apply a Pauli-Z gate on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the Z gate to.
    """
    broadcast.z(ilist.IList([qubit]))


@kernel
def s(qubit: qubit.Qubit):
    """Apply an S gate on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the S gate to.
    """
    broadcast.s(ilist.IList([qubit]))


@kernel
def s_dag(qubit: qubit.Qubit):
    """Apply the adjoint of the S gate on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the adjoint S gate to.
    """
    broadcast.s_adj(ilist.IList([qubit]))


@kernel
def h(qubit: qubit.Qubit):
    """Apply a Hadamard gate on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the Hadamard gate to.
    """
    broadcast.h(ilist.IList([qubit]))


@kernel
def t(qubit: qubit.Qubit):
    """Apply a T gate on a single qubit.

    Args:
        qubit (qubit.Qubit): The qubit to apply the T gate to.
    """
    broadcast.t(ilist.IList([qubit]))


@kernel
def shift(angle: float, qubit: qubit.Qubit):
    """Apply a phase shift on the |1> state of a single qubit.

    Args:
        angle (float): Shift angle in radians.
        qubit (qubit.Qubit): The qubit to apply the shift to.
    """
    broadcast.shift(angle, ilist.IList([qubit]))


@kernel
def rot(phi: float, theta: float, omega: float, qubit: qubit.Qubit):
    """Apply a general single-qubit rotation on a single qubit.

    Args:
        phi (float): Z rotation before Y (radians).
        theta (float): Y rotation (radians).
        omega (float): Z rotation after Y (radians).
        qubit (qubit.Qubit): The qubit to apply the rotation to.
    """
    broadcast.rot(phi, theta, omega, ilist.IList([qubit]))


@kernel
def u3(theta: float, phi: float, lam: float, qubit: qubit.Qubit):
    """Apply the U3 gate on a single qubit.

    Args:
        theta (float): Rotation angle around the Y axis in radians.
        phi (float): Rotation angle around the Z axis in radians.
        lam (float): Rotation angle around the Z axis in radians.
        qubit (qubit.Qubit): The qubit to apply the U3 gate to.
    """
    broadcast.u3(theta, phi, lam, ilist.IList([qubit]))


@kernel
def cz(control: qubit.Qubit, target: qubit.Qubit):
    """Apply a controlled-Z gate on two qubits.

    Args:
        control (qubit.Qubit): The control qubit.
        target (qubit.Qubit): The target qubit.
    """
    broadcast.cz(ilist.IList([control]), ilist.IList([target]))


@kernel
def cx(control: qubit.Qubit, target: qubit.Qubit):
    """Apply a controlled-X gate on two qubits.

    Args:
        control (qubit.Qubit): The control qubit.
        target (qubit.Qubit): The target qubit.
    """
    broadcast.cx(ilist.IList([control]), ilist.IList([target]))


@kernel
def cy(control: qubit.Qubit, targets: qubit.Qubit):
    """Apply a controlled-Y gate on two qubits.

    Args:
        control (qubit.Qubit): The control qubit.
        targets (qubit.Qubit): The target qubit.
    """
    broadcast.cy(ilist.IList([control]), ilist.IList([targets]))
