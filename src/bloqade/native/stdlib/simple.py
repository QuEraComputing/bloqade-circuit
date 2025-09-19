import math

from kirin.dialects import ilist

from bloqade.squin import qubit
from bloqade.native._prelude import kernel
from bloqade.native.dialects.gates import _interface as native


@kernel
def rx(angle: float, qubit: qubit.Qubit):
    native.r(ilist.IList([qubit]), 0.0, angle / (2 * math.pi))


@kernel
def x(qubit: qubit.Qubit):
    rx(math.pi, qubit)


@kernel
def sqrt_x(qubit: qubit.Qubit):
    rx(math.pi / 2.0, qubit)


@kernel
def sqrt_x_dag(qubit: qubit.Qubit):
    rx(-math.pi / 2.0, qubit)


@kernel
def ry(angle: float, qubit: qubit.Qubit):
    native.r(ilist.IList([qubit]), 0.25, angle / (2 * math.pi))


@kernel
def y(qubit: qubit.Qubit):
    ry(math.pi, qubit)


@kernel
def sqrt_y(qubit: qubit.Qubit):
    ry(math.pi / 2.0, qubit)


@kernel
def sqrt_y_dag(qubit: qubit.Qubit):
    ry(-math.pi / 2.0, qubit)


@kernel
def rz(angle: float, qubit: qubit.Qubit):
    native.rz(ilist.IList([qubit]), angle / (2 * math.pi))


@kernel
def z(qubit: qubit.Qubit):
    rz(math.pi, qubit)


@kernel
def s(qubit: qubit.Qubit):
    rz(math.pi / 2.0, qubit)


@kernel
def s_dag(qubit: qubit.Qubit):
    rz(-math.pi / 2.0, qubit)


@kernel
def h(qubit: qubit.Qubit):
    s(qubit)
    sqrt_x(qubit)
    s(qubit)


@kernel
def t(qubit: qubit.Qubit):
    rz(math.pi / 4.0, qubit)


@kernel
def shift(angle: float, qubit: qubit.Qubit):
    rz(angle / 2.0, qubit)


@kernel
def rot(phi: float, theta: float, omega: float, qubit: qubit.Qubit):
    rz(phi, qubit)
    ry(theta, qubit)
    rz(omega, qubit)


@kernel
def u3(theta: float, phi: float, lam: float, qubit: qubit.Qubit):
    rot(lam, theta, -lam, qubit)
    shift(phi + lam, qubit)


@kernel
def cz(control: qubit.Qubit, target: qubit.Qubit):
    native.cz(ilist.IList([control]), ilist.IList([target]))


@kernel
def cx(control: qubit.Qubit, target: qubit.Qubit):
    sqrt_y_dag(target)
    cz(control, target)
    sqrt_y(target)


@kernel
def cy(control: qubit.Qubit, targets: qubit.Qubit):
    sqrt_x(targets)
    cz(control, targets)
    sqrt_x_dag(targets)


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
