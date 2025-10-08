from kirin.dialects import ilist

from bloqade.types import Qubit

from .. import broadcast
from ...groups import kernel


@kernel
def x(qubit: Qubit) -> None:
    """Apply a Pauli-X gate to a qubit.

    Args:
        qubit (Qubit): Target qubit.
    """
    broadcast.x(ilist.IList([qubit]))


@kernel
def y(qubit: Qubit) -> None:
    """Apply a Pauli-Y gate to a qubit.

    Args:
        qubit (Qubit): Target qubit.
    """
    broadcast.y(ilist.IList([qubit]))


@kernel
def z(qubit: Qubit) -> None:
    """Apply a Pauli-Z gate to a qubit.

    Args:
        qubit (Qubit): Target qubit.
    """
    broadcast.z(ilist.IList([qubit]))


@kernel
def h(qubit: Qubit) -> None:
    """Apply a Hadamard gate to a qubit.

    Args:
        qubit (Qubit): Target qubit.
    """
    broadcast.h(ilist.IList([qubit]))


@kernel
def t(qubit: Qubit) -> None:
    """Apply a T gate to a qubit.

    Args:
        qubit (Qubit): Target qubit.
    """
    broadcast.t(ilist.IList([qubit]))


@kernel
def s(qubit: Qubit) -> None:
    """Apply an S gate to a qubit.

    Args:
        qubit (Qubit): Target qubit.
    """
    broadcast.s(ilist.IList([qubit]))


@kernel
def sqrt_x(qubit: Qubit) -> None:
    """Apply a Sqrt(X) gate to a qubit.

    Args:
        qubit (Qubit): Target qubit.
    """
    broadcast.sqrt_x(ilist.IList([qubit]))


@kernel
def sqrt_y(qubit: Qubit) -> None:
    """Apply a Sqrt(Y) gate to a qubit.

    Args:
        qubit (Qubit): Target qubit.
    """
    broadcast.sqrt_y(ilist.IList([qubit]))


@kernel
def sqrt_z(qubit: Qubit) -> None:
    """Apply a Sqrt(Z) gate to a qubit.

    Args:
        qubit (Qubit): Target qubit.
    """
    broadcast.s(ilist.IList([qubit]))


@kernel
def t_adj(qubit: Qubit) -> None:
    """Apply the adjoint of a T gate to a qubit.

    Args:
        qubit (Qubit): Target qubit.
    """
    broadcast.t_adj(ilist.IList([qubit]))


@kernel
def s_adj(qubit: Qubit) -> None:
    """Apply the adjoint of an S gate to a qubit.

    Args:
        qubit (Qubit): Target qubit.
    """
    broadcast.s_adj(ilist.IList([qubit]))


@kernel
def sqrt_x_adj(qubit: Qubit) -> None:
    """Apply the adjoint of a Sqrt(X) gate to a qubit.

    Args:
        qubit (Qubit): Target qubit.
    """
    broadcast.sqrt_x_adj(ilist.IList([qubit]))


@kernel
def sqrt_y_adj(qubit: Qubit) -> None:
    """Apply the adjoint of a Sqrt(Y) gate to a qubit.

    Args:
        qubit (Qubit): Target qubit.
    """
    broadcast.sqrt_y_adj(ilist.IList([qubit]))


@kernel
def sqrt_z_adj(qubit: Qubit) -> None:
    """Apply the adjoint of a Sqrt(Z) gate to a qubit.

    Args:
        qubit (Qubit): Target qubit.
    """
    broadcast.s_adj(ilist.IList([qubit]))


@kernel
def rx(angle: float, qubit: Qubit) -> None:
    """Apply an RX rotation gate to a qubit.

    Args:
        angle (float): Rotation angle in radians.
        qubit (Qubit): Target qubit.
    """
    broadcast.rx(angle, ilist.IList([qubit]))


@kernel
def ry(angle: float, qubit: Qubit) -> None:
    """Apply an RY rotation gate to a qubit.

    Args:
        angle (float): Rotation angle in radians.
        qubit (Qubit): Target qubit.
    """
    broadcast.ry(angle, ilist.IList([qubit]))


@kernel
def rz(angle: float, qubit: Qubit) -> None:
    """Apply an RZ rotation gate to a qubit.

    Args:
        angle (float): Rotation angle in radians.
        qubit (Qubit): Target qubit.
    """
    broadcast.rz(angle, ilist.IList([qubit]))


@kernel
def cx(control: Qubit, target: Qubit) -> None:
    """Apply a controlled-X gate to a pair of qubits.

    Args:
        controls (Qubit): Control qubit.
        targets (Qubit): Target qubit.
    """
    broadcast.cx(ilist.IList([control]), ilist.IList([target]))


@kernel
def cy(control: Qubit, target: Qubit) -> None:
    """Apply a controlled-Y gate to a pair of qubits.

    Args:
        controls (Qubit): Control qubit.
        targets (Qubit): Target qubit.
    """
    broadcast.cy(ilist.IList([control]), ilist.IList([target]))


@kernel
def cz(control: Qubit, target: Qubit) -> None:
    """Apply a controlled-Z gate to a pair of qubits.

    Args:
        controls (Qubit): Control qubit.
        targets (Qubit): Target qubit.
    """
    broadcast.cz(ilist.IList([control]), ilist.IList([target]))


@kernel
def u3(theta: float, phi: float, lam: float, qubit: Qubit):
    """Apply the U3 gate of a qubit.

    The applied gate is represented by the unitary matrix given by:

    $$ U3(\\theta, \\phi, \\lambda) = R_z(\\phi)R_y(\\theta)R_z(\\lambda) $$

    Args:
        theta (float): Rotation around Y axis (radians).
        phi (float): Global phase shift component (radians).
        lam (float): Z rotations in decomposition (radians).
        qubit (Qubit): Target qubit.
    """
    broadcast.u3(theta, phi, lam, ilist.IList([qubit]))


# NOTE: stdlib not wrapping statements starts here


@kernel
def shift(angle: float, qubit: Qubit) -> None:
    """Apply a phase shift to the |1> state of a qubit.
    Args:
        angle (float): Phase shift angle in radians.
        qubit (Qubit): Target qubit.
    """
    broadcast.shift(angle, ilist.IList([qubit]))


@kernel
def rot(phi: float, theta: float, omega: float, qubit: Qubit):
    """Apply a general single-qubit rotation of a qubit.

    The applied gate is represented by the unitary matrix given by:

    $$ R_z(\\omega)R_y(\\theta)R_z(\\phi) $$

    Args:
        phi (float): Z rotation before Y (radians).
        theta (float): Y rotation (radians).
        omega (float): Z rotation after Y (radians).
        qubit (Qubit): Target qubit.
    """
    broadcast.rot(phi, theta, omega, ilist.IList([qubit]))
