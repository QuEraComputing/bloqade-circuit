import math
from typing import Any, TypeVar

from kirin.dialects import ilist

from bloqade.squin import qubit
from bloqade.native import kernel
from bloqade.native.dialects.gates import _interface as native


@kernel
def _radian_to_turn(angle: float) -> float:
    """Rescale angle from radians to turns."""
    return angle / (2 * math.pi)


@kernel
def rx(angle: float, qubits: ilist.IList[qubit.Qubit, Any]):
    native.r(qubits, 0.0, _radian_to_turn(angle))


@kernel
def x(qubits: ilist.IList[qubit.Qubit, Any]):
    rx(math.pi, qubits)


@kernel
def sqrt_x(qubits: ilist.IList[qubit.Qubit, Any]):
    rx(math.pi / 2.0, qubits)


@kernel
def sqrt_x_dag(qubits: ilist.IList[qubit.Qubit, Any]):
    rx(-math.pi / 2.0, qubits)


@kernel
def ry(angle: float, qubits: ilist.IList[qubit.Qubit, Any]):
    native.r(qubits, 0.25, _radian_to_turn(angle))


@kernel
def y(qubits: ilist.IList[qubit.Qubit, Any]):
    ry(math.pi, qubits)


@kernel
def sqrt_y(qubits: ilist.IList[qubit.Qubit, Any]):
    ry(math.pi / 2.0, qubits)


@kernel
def sqrt_y_dag(qubits: ilist.IList[qubit.Qubit, Any]):
    ry(-math.pi / 2.0, qubits)


@kernel
def rz(angle: float, qubits: ilist.IList[qubit.Qubit, Any]):
    native.rz(qubits, _radian_to_turn(angle))


@kernel
def z(qubits: ilist.IList[qubit.Qubit, Any]):
    rz(math.pi, qubits)


@kernel
def s(qubits: ilist.IList[qubit.Qubit, Any]):
    rz(math.pi / 2.0, qubits)


@kernel
def s_dag(qubits: ilist.IList[qubit.Qubit, Any]):
    rz(-math.pi / 2.0, qubits)


@kernel
def h(qubits: ilist.IList[qubit.Qubit, Any]):
    s(qubits)
    sqrt_x(qubits)
    s(qubits)


@kernel
def t(qubits: ilist.IList[qubit.Qubit, Any]):
    rz(math.pi / 4.0, qubits)


@kernel
def shift(angle: float, qubits: ilist.IList[qubit.Qubit, Any]):
    rz(angle / 2.0, qubits)


@kernel
def rot(phi: float, theta: float, omega: float, qubits: ilist.IList[qubit.Qubit, Any]):
    rz(phi, qubits)
    ry(theta, qubits)
    rz(omega, qubits)


@kernel
def u3(theta: float, phi: float, lam: float, qubits: ilist.IList[qubit.Qubit, Any]):
    rot(lam, theta, -lam, qubits)
    shift(phi + lam, qubits)


N = TypeVar("N")


@kernel
def cz(controls: ilist.IList[qubit.Qubit, N], qubits: ilist.IList[qubit.Qubit, N]):
    native.cz(controls, qubits)


@kernel
def cx(controls: ilist.IList[qubit.Qubit, N], targets: ilist.IList[qubit.Qubit, N]):
    sqrt_y_dag(targets)
    cz(controls, targets)
    sqrt_y(targets)


@kernel
def cy(controls: ilist.IList[qubit.Qubit, N], targets: ilist.IList[qubit.Qubit, N]):
    sqrt_x(targets)
    cz(controls, targets)
    sqrt_x_dag(targets)
