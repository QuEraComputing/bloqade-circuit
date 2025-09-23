from kirin.dialects import ilist

from bloqade.squin import qubit

from . import broadcast
from .._prelude import kernel


@kernel
def rx(angle: float, qubit: qubit.Qubit):
    broadcast.rx(angle, ilist.IList([qubit]))


@kernel
def x(qubit: qubit.Qubit):
    broadcast.x(ilist.IList([qubit]))


@kernel
def sqrt_x(qubit: qubit.Qubit):
    broadcast.sqrt_x(ilist.IList([qubit]))


@kernel
def sqrt_x_dag(qubit: qubit.Qubit):
    broadcast.sqrt_x_adj(ilist.IList([qubit]))


@kernel
def ry(angle: float, qubit: qubit.Qubit):
    broadcast.ry(angle, ilist.IList([qubit]))


@kernel
def y(qubit: qubit.Qubit):
    broadcast.y(ilist.IList([qubit]))


@kernel
def sqrt_y(qubit: qubit.Qubit):
    broadcast.sqrt_y(ilist.IList([qubit]))


@kernel
def sqrt_y_dag(qubit: qubit.Qubit):
    broadcast.sqrt_y_adj(ilist.IList([qubit]))


@kernel
def rz(angle: float, qubit: qubit.Qubit):
    broadcast.rz(angle, ilist.IList([qubit]))


@kernel
def z(qubit: qubit.Qubit):
    broadcast.z(ilist.IList([qubit]))


@kernel
def s(qubit: qubit.Qubit):
    broadcast.s(ilist.IList([qubit]))


@kernel
def s_dag(qubit: qubit.Qubit):
    broadcast.s_adj(ilist.IList([qubit]))


@kernel
def h(qubit: qubit.Qubit):
    broadcast.h(ilist.IList([qubit]))


@kernel
def t(qubit: qubit.Qubit):
    broadcast.t(ilist.IList([qubit]))


@kernel
def shift(angle: float, qubit: qubit.Qubit):
    broadcast.shift(angle, ilist.IList([qubit]))


@kernel
def rot(phi: float, theta: float, omega: float, qubit: qubit.Qubit):
    broadcast.rot(phi, theta, omega, ilist.IList([qubit]))


@kernel
def u3(theta: float, phi: float, lam: float, qubit: qubit.Qubit):
    broadcast.u3(theta, phi, lam, ilist.IList([qubit]))


@kernel
def cz(control: qubit.Qubit, target: qubit.Qubit):
    broadcast.cz(ilist.IList([control]), ilist.IList([target]))


@kernel
def cx(control: qubit.Qubit, target: qubit.Qubit):
    broadcast.cx(ilist.IList([control]), ilist.IList([target]))


@kernel
def cy(control: qubit.Qubit, targets: qubit.Qubit):
    broadcast.cy(ilist.IList([control]), ilist.IList([targets]))


__all__ = [
    "x",
    "y",
    "z",
    "s",
    "h",
    "t",
    "s_dag",
    "sqrt_x",
    "sqrt_x_dag",
    "sqrt_y",
    "sqrt_y_dag",
    "rx",
    "ry",
    "rz",
    "cz",
    "cx",
    "cy",
    "shift",
    "rot",
    "u3",
]
