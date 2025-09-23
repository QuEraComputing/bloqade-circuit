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
