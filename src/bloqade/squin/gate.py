from kirin import ir
from kirin.prelude import structural_no_opt

from bloqade.types import Qubit

from . import op as _op, qubit as _qubit


@ir.dialect_group(structural_no_opt.union([_qubit, _op]))
def _apply(self):
    def run_pass(method):
        pass

    return run_pass


@_apply
def x(qubit: Qubit) -> None:
    op = _op.x()
    _qubit.apply(op, qubit)


@_apply
def y(qubit: Qubit) -> None:
    op = _op.y()
    _qubit.apply(op, qubit)


@_apply
def z(qubit: Qubit) -> None:
    op = _op.z()
    _qubit.apply(op, qubit)


@_apply
def sqrt_x(qubit: Qubit) -> None:
    op = _op.sqrt_x()
    _qubit.apply(op, qubit)


@_apply
def sqrt_y(qubit: Qubit) -> None:
    op = _op.sqrt_y()
    _qubit.apply(op, qubit)


@_apply
def sqrt_z(qubit: Qubit) -> None:
    op = _op.s()
    _qubit.apply(op, qubit)


@_apply
def h(qubit: Qubit) -> None:
    op = _op.h()
    _qubit.apply(op, qubit)


@_apply
def s(qubit: Qubit) -> None:
    op = _op.s()
    _qubit.apply(op, qubit)


@_apply
def t(qubit: Qubit) -> None:
    op = _op.t()
    _qubit.apply(op, qubit)


@_apply
def p0(qubit: Qubit) -> None:
    op = _op.p0()
    _qubit.apply(op, qubit)


@_apply
def p1(qubit: Qubit) -> None:
    op = _op.p1()
    _qubit.apply(op, qubit)


@_apply
def spin_n(qubit: Qubit) -> None:
    op = _op.spin_n()
    _qubit.apply(op, qubit)


@_apply
def spin_p(qubit: Qubit) -> None:
    op = _op.spin_p()
    _qubit.apply(op, qubit)


@_apply
def reset(qubit: Qubit) -> None:
    op = _op.reset()
    _qubit.apply(op, qubit)


@_apply
def cx(control: Qubit, target: Qubit) -> None:
    op = _op.cx()
    _qubit.apply(op, control, target)


@_apply
def cy(control: Qubit, target: Qubit) -> None:
    op = _op.cy()
    _qubit.apply(op, control, target)


@_apply
def cz(control: Qubit, target: Qubit) -> None:
    op = _op.cz()
    _qubit.apply(op, control, target)


@_apply
def ch(control: Qubit, target: Qubit) -> None:
    op = _op.ch()
    _qubit.apply(op, control, target)
