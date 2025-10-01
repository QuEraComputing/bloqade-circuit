import math
from typing import Any, TypeVar

from kirin.dialects import ilist

from bloqade.types import Qubit

from ...groups import kernel
from ...clifford import _interface as clifford


@kernel
def _radian_to_turn(angle: float) -> float:
    """Convert an angle from radians to turns.

    Args:
        angle (float): Angle in radians.
    Returns:
        float: Equivalent angle in turns.
    """
    return angle / (2 * math.pi)


@kernel
def x(qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply a Pauli-X gate to a group of qubits.

    Args:
        qubits (ilist.IList[Qubit, Any]): Target qubits.
    """
    clifford.x(qubits)


@kernel
def y(qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply a Pauli-Y gate to a group of qubits.

    Args:
        qubits (ilist.IList[Qubit, Any]): Target qubits.
    """
    clifford.y(qubits)


@kernel
def z(qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply a Pauli-Z gate to a group of qubits.

    Args:
        qubits (ilist.IList[Qubit, Any]): Target qubits.
    """
    clifford.z(qubits)


@kernel
def h(qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply a Hadamard gate to a group of qubits.

    Args:
        qubits (ilist.IList[Qubit, Any]): Target qubits.
    """
    clifford.h(qubits)


@kernel
def t(qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply a T gate to a group of qubits.

    Args:
        qubits (ilist.IList[Qubit, Any]): Target qubits.
    """
    clifford.t(qubits, adjoint=False)


@kernel
def s(qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply an S gate to a group of qubits.

    Args:
        qubits (ilist.IList[Qubit, Any]): Target qubits.
    """
    clifford.s(qubits, adjoint=False)


@kernel
def sqrt_x(qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply a Sqrt(X) gate to a group of qubits.

    Args:
        qubits (ilist.IList[Qubit, Any]): Target qubits.
    """
    clifford.sqrt_x(qubits, adjoint=False)


@kernel
def sqrt_y(qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply a sqrt(Y) gate to a group of qubits.

    Args:
        qubits (ilist.IList[Qubit, Any]): Target qubits.
    """
    clifford.sqrt_y(qubits, adjoint=False)


@kernel
def sqrt_z(qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply a Sqrt(Z) gate to a group of qubits.

    Args:
        qubits (ilist.IList[Qubit, Any]): Target qubits.
    """
    clifford.s(qubits, adjoint=False)


@kernel
def t_adj(qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply the adjoint of a T gate to a group of qubits.

    Args:
        qubits (ilist.IList[Qubit, Any]): Target qubits.
    """
    clifford.t(qubits, adjoint=True)


@kernel
def s_adj(qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply the adjoint of an S gate to a group of qubits.

    Args:
        qubits (ilist.IList[Qubit, Any]): Target qubits.
    """
    clifford.s(qubits, adjoint=True)


@kernel
def sqrt_x_adj(qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply the adjoint of a Sqrt(X) gate to a group of qubits.

    Args:
        qubits (ilist.IList[Qubit, Any]): Target qubits.
    """
    clifford.sqrt_x(qubits, adjoint=True)


@kernel
def sqrt_y_adj(qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply the adjoint of a Sqrt(Y) gate to a group of qubits.

    Args:
        qubits (ilist.IList[Qubit, Any]): Target qubits.
    """
    clifford.sqrt_y(qubits, adjoint=True)


@kernel
def sqrt_z_adj(qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply the adjoint of a Sqrt(Z) gate to a group of qubits.

    Args:
        qubits (ilist.IList[Qubit, Any]): Target qubits.
    """
    clifford.s(qubits, adjoint=True)


@kernel
def rx(angle: float, qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply an RX rotation gate to a group of qubits.

    Args:
        angle (float): Rotation angle in radians.
        qubits (ilist.IList[Qubit, Any]): Target qubits.
    """
    clifford.rx(_radian_to_turn(angle), qubits)


@kernel
def ry(angle: float, qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply an RY rotation gate to a group of qubits.

    Args:
        angle (float): Rotation angle in radians.
        qubits (ilist.IList[Qubit, Any]): Target qubits.
    """
    clifford.ry(_radian_to_turn(angle), qubits)


@kernel
def rz(angle: float, qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply an RZ rotation gate to a group of qubits.

    Args:
        angle (float): Rotation angle in radians.
        qubits (ilist.IList[Qubit, Any]): Target qubits.
    """
    clifford.rz(_radian_to_turn(angle), qubits)


Len = TypeVar("Len", bound=int)


@kernel
def cx(controls: ilist.IList[Qubit, Len], targets: ilist.IList[Qubit, Len]) -> None:
    """Apply a controlled-X gate to pairs of qubits.

    Args:
        controls (ilist.IList[Qubit, N]): Control qubits.
        targets (ilist.IList[Qubit, N]): Target qubits.
    """
    clifford.cx(controls, targets)


@kernel
def cy(controls: ilist.IList[Qubit, Len], targets: ilist.IList[Qubit, Len]) -> None:
    """Apply a controlled-Y gate to pairs of qubits.

    Args:
        controls (ilist.IList[Qubit, N]): Control qubits.
        targets (ilist.IList[Qubit, N]): Target qubits.
    """
    clifford.cy(controls, targets)


@kernel
def cz(controls: ilist.IList[Qubit, Len], targets: ilist.IList[Qubit, Len]) -> None:
    """Apply a controlled-Z gate to pairs of qubits.

    Args:
        controls (ilist.IList[Qubit, N]): Control qubits.
        targets (ilist.IList[Qubit, N]): Target qubits.
    """
    clifford.cz(controls, targets)


# NOTE: stdlib not wrapping statements starts here


@kernel
def shift(angle: float, qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply a phase shift to the |1> state to a group of qubits.
    Args:
        angle (float): Phase shift angle in radians.
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
    """
    rz(angle / 2.0, qubits)


@kernel
def rot(phi: float, theta: float, omega: float, qubits: ilist.IList[Qubit, Any]):
    """Apply a general single-qubit rotation to a group of qubits.
    Args:
        phi (float): Z rotation before Y (radians).
        theta (float): Y rotation (radians).
        omega (float): Z rotation after Y (radians).
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
    """
    rz(phi, qubits)
    ry(theta, qubits)
    rz(omega, qubits)


@kernel
def u3(theta: float, phi: float, lam: float, qubits: ilist.IList[Qubit, Any]):
    """Apply the U3 gate to a group of qubits.
    Args:
        theta (float): Rotation around Y axis (radians).
        phi (float): Global phase shift component (radians).
        lam (float): Z rotations in decomposition (radians).
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
    """
    rot(lam, theta, -lam, qubits)
    shift(phi + lam, qubits)
