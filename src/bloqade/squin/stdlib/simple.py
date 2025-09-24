from kirin.dialects import ilist

from bloqade.types import Qubit

from . import broadcast
from ..groups import kernel


@kernel
def x(qubit: Qubit) -> None:
    broadcast.x(ilist.IList([qubit]))


@kernel
def y(qubit: Qubit) -> None:
    broadcast.y(ilist.IList([qubit]))


@kernel
def z(qubit: Qubit) -> None:
    broadcast.z(ilist.IList([qubit]))


@kernel
def h(qubit: Qubit) -> None:
    broadcast.h(ilist.IList([qubit]))


@kernel
def t(qubit: Qubit) -> None:
    broadcast.t(ilist.IList([qubit]))


@kernel
def s(qubit: Qubit) -> None:
    broadcast.s(ilist.IList([qubit]))


@kernel
def sqrt_x(qubit: Qubit) -> None:
    broadcast.sqrt_x(ilist.IList([qubit]))


@kernel
def sqrt_y(qubit: Qubit) -> None:
    broadcast.sqrt_y(ilist.IList([qubit]))


@kernel
def sqrt_z(qubit: Qubit) -> None:
    broadcast.s(ilist.IList([qubit]))


@kernel
def t_adj(qubit: Qubit) -> None:
    broadcast.t_adj(ilist.IList([qubit]))


@kernel
def s_adj(qubit: Qubit) -> None:
    broadcast.s_adj(ilist.IList([qubit]))


@kernel
def sqrt_x_adj(qubit: Qubit) -> None:
    broadcast.sqrt_x_adj(ilist.IList([qubit]))


@kernel
def sqrt_y_adj(qubit: Qubit) -> None:
    broadcast.sqrt_y_adj(ilist.IList([qubit]))


@kernel
def sqrt_z_adj(qubit: Qubit) -> None:
    broadcast.s_adj(ilist.IList([qubit]))


@kernel
def rx(angle: float, qubit: Qubit) -> None:
    broadcast.rx(angle, ilist.IList([qubit]))


@kernel
def ry(angle: float, qubit: Qubit) -> None:
    broadcast.ry(angle, ilist.IList([qubit]))


@kernel
def rz(angle: float, qubit: Qubit) -> None:
    broadcast.rz(angle, ilist.IList([qubit]))


@kernel
def cx(control: Qubit, target: Qubit) -> None:
    broadcast.cx(ilist.IList([control]), ilist.IList([target]))


@kernel
def cy(control: Qubit, target: Qubit) -> None:
    broadcast.cy(ilist.IList([control]), ilist.IList([target]))


@kernel
def cz(control: Qubit, target: Qubit) -> None:
    broadcast.cz(ilist.IList([control]), ilist.IList([target]))
