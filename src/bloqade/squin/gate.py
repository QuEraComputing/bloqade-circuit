from bloqade.types import Qubit

from . import op as _op, qubit as _qubit
from .groups import kernel


@kernel
def x(qubit: Qubit) -> None:
    op = _op.x()
    _qubit.apply(op, qubit)


@kernel
def y(qubit: Qubit) -> None:
    op = _op.y()
    _qubit.apply(op, qubit)


@kernel
def z(qubit: Qubit) -> None:
    op = _op.z()
    _qubit.apply(op, qubit)


@kernel
def sqrt_x(qubit: Qubit) -> None:
    op = _op.sqrt_x()
    _qubit.apply(op, qubit)


@kernel
def sqrt_y(qubit: Qubit) -> None:
    op = _op.sqrt_y()
    _qubit.apply(op, qubit)


@kernel
def sqrt_z(qubit: Qubit) -> None:
    op = _op.s()
    _qubit.apply(op, qubit)


@kernel
def h(qubit: Qubit) -> None:
    op = _op.h()
    _qubit.apply(op, qubit)


@kernel
def s(qubit: Qubit) -> None:
    op = _op.s()
    _qubit.apply(op, qubit)


@kernel
def t(qubit: Qubit) -> None:
    op = _op.t()
    _qubit.apply(op, qubit)


@kernel
def p0(qubit: Qubit) -> None:
    op = _op.p0()
    _qubit.apply(op, qubit)


@kernel
def p1(qubit: Qubit) -> None:
    op = _op.p1()
    _qubit.apply(op, qubit)


@kernel
def spin_n(qubit: Qubit) -> None:
    op = _op.spin_n()
    _qubit.apply(op, qubit)


@kernel
def spin_p(qubit: Qubit) -> None:
    op = _op.spin_p()
    _qubit.apply(op, qubit)


@kernel
def reset(qubit: Qubit) -> None:
    op = _op.reset()
    _qubit.apply(op, qubit)


@kernel
def cx(control: Qubit, target: Qubit) -> None:
    op = _op.cx()
    _qubit.apply(op, control, target)


@kernel
def cy(control: Qubit, target: Qubit) -> None:
    op = _op.cy()
    _qubit.apply(op, control, target)


@kernel
def cz(control: Qubit, target: Qubit) -> None:
    op = _op.cz()
    _qubit.apply(op, control, target)


@kernel
def ch(control: Qubit, target: Qubit) -> None:
    op = _op.ch()
    _qubit.apply(op, control, target)
