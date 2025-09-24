import math

from kirin.dialects import ilist

from bloqade.types import Qubit

from ..groups import kernel
from ..clifford import _interface as clifford


@kernel
def _radian_to_turn(angle: float) -> float:
    """Rescale angle from radians to turns."""
    return angle / (2 * math.pi)


@kernel
def x(qubit: Qubit) -> None:
    clifford.x(ilist.IList([qubit]))


@kernel
def y(qubit: Qubit) -> None:
    clifford.y(ilist.IList([qubit]))


@kernel
def z(qubit: Qubit) -> None:
    clifford.z(ilist.IList([qubit]))


@kernel
def h(qubit: Qubit) -> None:
    clifford.h(ilist.IList([qubit]))


@kernel
def t(qubit: Qubit) -> None:
    clifford.t(ilist.IList([qubit]), adjoint=False)


@kernel
def s(qubit: Qubit) -> None:
    clifford.s(ilist.IList([qubit]), adjoint=False)


@kernel
def sqrt_x(qubit: Qubit) -> None:
    clifford.sqrt_x(ilist.IList([qubit]), adjoint=False)


@kernel
def sqrt_y(qubit: Qubit) -> None:
    clifford.sqrt_y(ilist.IList([qubit]), adjoint=False)


@kernel
def sqrt_z(qubit: Qubit) -> None:
    clifford.s(ilist.IList([qubit]), adjoint=False)


@kernel
def t_adj(qubit: Qubit) -> None:
    clifford.t(ilist.IList([qubit]), adjoint=True)


@kernel
def s_adj(qubit: Qubit) -> None:
    clifford.s(ilist.IList([qubit]), adjoint=True)


@kernel
def sqrt_x_adj(qubit: Qubit) -> None:
    clifford.sqrt_x(ilist.IList([qubit]), adjoint=True)


@kernel
def sqrt_y_adj(qubit: Qubit) -> None:
    clifford.sqrt_y(ilist.IList([qubit]), adjoint=True)


@kernel
def sqrt_z_adj(qubit: Qubit) -> None:
    clifford.s(ilist.IList([qubit]), adjoint=True)


@kernel
def rx(angle: float, qubit: Qubit) -> None:
    clifford.rx(_radian_to_turn(angle), ilist.IList([qubit]))


@kernel
def ry(angle: float, qubit: Qubit) -> None:
    clifford.ry(_radian_to_turn(angle), ilist.IList([qubit]))


@kernel
def rz(angle: float, qubit: Qubit) -> None:
    clifford.rz(_radian_to_turn(angle), ilist.IList([qubit]))


@kernel
def cx(control: Qubit, target: Qubit) -> None:
    clifford.cx(ilist.IList([control]), ilist.IList([target]))


@kernel
def cy(control: Qubit, target: Qubit) -> None:
    clifford.cy(ilist.IList([control]), ilist.IList([target]))


@kernel
def cz(control: Qubit, target: Qubit) -> None:
    clifford.cz(ilist.IList([control]), ilist.IList([target]))
