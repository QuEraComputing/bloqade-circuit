import math
from typing import Any, TypeVar

from kirin.dialects import ilist

from bloqade.types import Qubit

from ..groups import kernel
from ..clifford import _interface as clifford


@kernel
def _radian_to_turn(angle: float) -> float:
    """Rescale angle from radians to turns."""
    return angle / (2 * math.pi)


@kernel
def x(qubits: ilist.IList[Qubit, Any]) -> None:
    clifford.x(qubits)


@kernel
def y(qubits: ilist.IList[Qubit, Any]) -> None:
    clifford.y(qubits)


@kernel
def z(qubits: ilist.IList[Qubit, Any]) -> None:
    clifford.z(qubits)


@kernel
def h(qubits: ilist.IList[Qubit, Any]) -> None:
    clifford.h(qubits)


@kernel
def t(qubits: ilist.IList[Qubit, Any]) -> None:
    clifford.t(qubits, adjoint=False)


@kernel
def s(qubits: ilist.IList[Qubit, Any]) -> None:
    clifford.s(qubits, adjoint=False)


@kernel
def sqrt_x(qubits: ilist.IList[Qubit, Any]) -> None:
    clifford.sqrt_x(qubits, adjoint=False)


@kernel
def sqrt_y(qubits: ilist.IList[Qubit, Any]) -> None:
    clifford.sqrt_y(qubits, adjoint=False)


@kernel
def sqrt_z(qubits: ilist.IList[Qubit, Any]) -> None:
    clifford.s(qubits, adjoint=False)


@kernel
def t_adj(qubits: ilist.IList[Qubit, Any]) -> None:
    clifford.t(qubits, adjoint=True)


@kernel
def s_adj(qubits: ilist.IList[Qubit, Any]) -> None:
    clifford.s(qubits, adjoint=True)


@kernel
def sqrt_x_adj(qubits: ilist.IList[Qubit, Any]) -> None:
    clifford.sqrt_x(qubits, adjoint=True)


@kernel
def sqrt_y_adj(qubits: ilist.IList[Qubit, Any]) -> None:
    clifford.sqrt_y(qubits, adjoint=True)


@kernel
def sqrt_z_adj(qubits: ilist.IList[Qubit, Any]) -> None:
    clifford.s(qubits, adjoint=True)


@kernel
def rx(angle: float, qubits: ilist.IList[Qubit, Any]) -> None:
    clifford.rx(_radian_to_turn(angle), qubits)


@kernel
def ry(angle: float, qubits: ilist.IList[Qubit, Any]) -> None:
    clifford.ry(_radian_to_turn(angle), qubits)


@kernel
def rz(angle: float, qubits: ilist.IList[Qubit, Any]) -> None:
    clifford.rz(_radian_to_turn(angle), qubits)


Len = TypeVar("Len", bound=int)


@kernel
def cx(controls: ilist.IList[Qubit, Len], targets: ilist.IList[Qubit, Len]) -> None:
    clifford.cx(controls, targets)


@kernel
def cy(controls: ilist.IList[Qubit, Len], targets: ilist.IList[Qubit, Len]) -> None:
    clifford.cy(controls, targets)


@kernel
def cz(controls: ilist.IList[Qubit, Len], targets: ilist.IList[Qubit, Len]) -> None:
    clifford.cz(controls, targets)


# NOTE: stdlib not wrapping statements starts here


@kernel
def shift(angle: float, qubits: ilist.IList[Qubit, Any]) -> None:
    """Apply a phase shift to the |1> state on a group of qubits.
    Args:
        angle (float): Phase shift angle in radians.
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
    """
    rz(angle / 2.0, qubits)


@kernel
def rot(phi: float, theta: float, omega: float, qubits: ilist.IList[Qubit, Any]):
    """Apply a general single-qubit rotation on a group of qubits.
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
    """Apply the U3 gate on a group of qubits.
    Args:
        theta (float): Rotation around Y axis (radians).
        phi (float): Global phase shift component (radians).
        lam (float): Z rotations in decomposition (radians).
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
    """
    rot(lam, theta, -lam, qubits)
    shift(phi + lam, qubits)
