import math

from bloqade.types import Qubit

from ..groups import kernel
from ..clifford import _interface as clifford


@kernel
def _radian_to_turn(angle: float) -> float:
    """Rescale angle from radians to turns."""
    return angle / (2 * math.pi)


@kernel
def x(qubit: Qubit) -> None:
    clifford.x([qubit])


@kernel
def y(qubit: Qubit) -> None:
    clifford.y([qubit])


@kernel
def z(qubit: Qubit) -> None:
    clifford.z([qubit])


@kernel
def h(qubit: Qubit) -> None:
    clifford.h([qubit])


@kernel
def t(qubit: Qubit) -> None:
    clifford.t([qubit])


@kernel
def s(qubit: Qubit) -> None:
    clifford.s([qubit])


@kernel
def sqrt_x(qubit: Qubit) -> None:
    clifford.sqrt_x([qubit])


@kernel
def sqrt_y(qubit: Qubit) -> None:
    clifford.sqrt_y([qubit])


@kernel
def rx(angle: float, qubit: Qubit) -> None:
    clifford.rx(_radian_to_turn(angle), [qubit])


@kernel
def ry(angle: float, qubit: Qubit) -> None:
    clifford.ry(_radian_to_turn(angle), [qubit])


@kernel
def rz(angle: float, qubit: Qubit) -> None:
    clifford.rz(_radian_to_turn(angle), [qubit])


@kernel
def cx(control: Qubit, target: Qubit) -> None:
    clifford.cx([control], [target])


@kernel
def cy(control: Qubit, target: Qubit) -> None:
    clifford.cy([control], [target])


@kernel
def cz(control: Qubit, target: Qubit) -> None:
    clifford.cz([control], [target])
