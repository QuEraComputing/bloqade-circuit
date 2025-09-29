import math
from typing import Any, TypeVar

from kirin.dialects import ilist

from bloqade.squin import qubit
from bloqade.native._prelude import kernel
from bloqade.native.dialects.gates import _interface as native


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
def rx(qubits: ilist.IList[qubit.Qubit, Any], angle: float):
    """Apply an RX rotation gate on a group of qubits.

    Args:
        angle (float): Rotation angle in radians.
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
    """
    native.r(qubits, 0.0, _radian_to_turn(angle))


@kernel
def x(qubits: ilist.IList[qubit.Qubit, Any]):
    """Apply a Pauli-X gate on a group of qubits.

    Args:
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
    """
    rx(angle=math.pi, qubits=qubits)


@kernel
def sqrt_x(qubits: ilist.IList[qubit.Qubit, Any]):
    """Apply a sqrt(X) gate on a group of qubits.

    Args:
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
    """
    rx(qubits=qubits, angle=math.pi / 2.0)


@kernel
def sqrt_x_adj(qubits: ilist.IList[qubit.Qubit, Any]):
    """Apply the adjoint of sqrt(X) on a group of qubits.

    Args:
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
    """
    rx(angle=-math.pi / 2.0, qubits=qubits)


@kernel
def ry(qubits: ilist.IList[qubit.Qubit, Any], angle: float):
    """Apply an RY rotation gate on a group of qubits.

    Args:
        angle (float): Rotation angle in radians.
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
    """
    native.r(qubits, 0.25, _radian_to_turn(angle))


@kernel
def y(qubits: ilist.IList[qubit.Qubit, Any]):
    """Apply a Pauli-Y gate on a group of qubits.

    Args:
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
    """
    ry(qubits, angle=math.pi)


@kernel
def sqrt_y(qubits: ilist.IList[qubit.Qubit, Any]):
    """Apply a sqrt(Y) gate on a group of qubits.

    Args:
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
    """
    ry(qubits, -math.pi / 2.0)


@kernel
def sqrt_y_adj(qubits: ilist.IList[qubit.Qubit, Any]):
    """Apply the adjoint of sqrt(Y) on a group of qubits.

    Args:
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
    """
    ry(qubits, math.pi / 2.0)


@kernel
def rz(qubits: ilist.IList[qubit.Qubit, Any], angle: float):
    """Apply an RZ rotation gate on a group of qubits.

    Args:
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
        angle (float): Rotation angle in radians.
    """
    native.rz(qubits, _radian_to_turn(angle))


@kernel
def z(qubits: ilist.IList[qubit.Qubit, Any]):
    """Apply a Pauli-Z gate on a group of qubits.

    Args:
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
    """
    rz(qubits, math.pi)


@kernel
def s(qubits: ilist.IList[qubit.Qubit, Any]):
    """Apply an S gate on a group of qubits.

    Args:
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
    """
    rz(qubits, math.pi / 2.0)


@kernel
def s_adj(qubits: ilist.IList[qubit.Qubit, Any]):
    """Apply the adjoint of the S gate on a group of qubits.

    Args:
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
    """
    rz(qubits, -math.pi / 2.0)


@kernel
def h(qubits: ilist.IList[qubit.Qubit, Any]):
    """Apply a Hadamard gate on a group of qubits.

    Args:
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
    """
    s(qubits)
    sqrt_x(qubits)
    s(qubits)


@kernel
def t(qubits: ilist.IList[qubit.Qubit, Any]):
    """Apply a T gate on a group of qubits.

    Args:
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
    """
    rz(qubits, math.pi / 4.0)


@kernel
def shift(qubits: ilist.IList[qubit.Qubit, Any], angle: float):
    """Apply a phase shift to the |1> state on a group of qubits.

    Args:
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
        angle (float): Phase shift angle in radians.

    """
    rz(qubits, angle / 2.0)


@kernel
def rot(qubits: ilist.IList[qubit.Qubit, Any], phi: float, theta: float, omega: float):
    """Apply a general single-qubit rotation on a group of qubits.

    Args:
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
        phi (float): Z rotation before Y (radians).
        theta (float): Y rotation (radians).
        omega (float): Z rotation after Y (radians).
    """
    rz(qubits, phi)
    ry(qubits, theta)
    rz(qubits, omega)


@kernel
def u3(qubits: ilist.IList[qubit.Qubit, Any], theta: float, phi: float, lam: float):
    """Apply the U3 gate on a group of qubits.

    Args:
        qubits (ilist.IList[qubit.Qubit, Any]): Target qubits.
        theta (float): Rotation around Y axis (radians).
        phi (float): Global phase shift component (radians).
        lam (float): Z rotations in decomposition (radians).
    """
    rot(qubits, lam, theta, -lam)
    shift(qubits, phi + lam)


N = TypeVar("N")


@kernel
def cz(controls: ilist.IList[qubit.Qubit, N], qubits: ilist.IList[qubit.Qubit, N]):
    """Apply a controlled-Z gate on a pairs of qubits.

    Args:
        controls (ilist.IList[qubit.Qubit, N]): Control qubits.
        qubits (ilist.IList[qubit.Qubit, N]): Target qubits.
    """
    native.cz(controls, qubits)


@kernel
def cx(controls: ilist.IList[qubit.Qubit, N], targets: ilist.IList[qubit.Qubit, N]):
    """Apply a controlled-X gate on a pairs of qubits.

    Args:
        controls (ilist.IList[qubit.Qubit, N]): Control qubits.
        targets (ilist.IList[qubit.Qubit, N]): Target qubits.
    """
    sqrt_y_adj(targets)
    cz(controls, targets)
    sqrt_y(targets)


@kernel
def cy(controls: ilist.IList[qubit.Qubit, N], targets: ilist.IList[qubit.Qubit, N]):
    """Apply a controlled-Y gate on a pairs of qubits.

    Args:
        controls (ilist.IList[qubit.Qubit, N]): Control qubits.
        targets (ilist.IList[qubit.Qubit, N]): Target qubits.
    """
    sqrt_x(targets)
    cz(controls, targets)
    sqrt_x_adj(targets)
