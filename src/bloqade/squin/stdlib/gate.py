from bloqade.types import Qubit

from ..groups import kernel

from .. import op as _op, qubit as _qubit  # isort: skip


@kernel
def x(qubit: Qubit) -> None:
    """x gate applied to qubit."""
    op = _op.x()
    _qubit.apply(op, qubit)


@kernel
def y(qubit: Qubit) -> None:
    """y gate applied to qubit."""
    op = _op.y()
    _qubit.apply(op, qubit)


@kernel
def z(qubit: Qubit) -> None:
    """z gate applied to qubit."""
    op = _op.z()
    _qubit.apply(op, qubit)


@kernel
def sqrt_x(qubit: Qubit) -> None:
    """Square root x gate applied to qubit."""
    op = _op.sqrt_x()
    _qubit.apply(op, qubit)


@kernel
def sqrt_x_adj(qubit: Qubit) -> None:
    """Adjoint sqrt_x gate applied to qubit."""
    op = _op.sqrt_x()
    _qubit.apply(_op.adjoint(op), qubit)


@kernel
def sqrt_y(qubit: Qubit) -> None:
    """Square root y gate applied to qubit."""
    op = _op.sqrt_y()
    _qubit.apply(op, qubit)


@kernel
def sqrt_y_adj(qubit: Qubit) -> None:
    """Adjoint sqrt_y gate applied to qubit."""
    op = _op.sqrt_y()
    _qubit.apply(_op.adjoint(op), qubit)


@kernel
def sqrt_z(qubit: Qubit) -> None:
    """Square root z gate applied to qubit."""
    op = _op.s()
    _qubit.apply(op, qubit)


@kernel
def sqrt_z_adj(qubit: Qubit) -> None:
    """Adjoint square root z gate applied to qubit."""
    op = _op.s()
    _qubit.apply(_op.adjoint(op), qubit)


@kernel
def h(qubit: Qubit) -> None:
    """Hadamard gate applied to qubit."""
    op = _op.h()
    _qubit.apply(op, qubit)


@kernel
def s(qubit: Qubit) -> None:
    """s gate applied to qubit."""
    op = _op.s()
    _qubit.apply(op, qubit)


@kernel
def s_adj(qubit: Qubit) -> None:
    """Adjoint s gate applied to qubit."""
    op = _op.s()
    _qubit.apply(_op.adjoint(op), qubit)


@kernel
def t(qubit: Qubit) -> None:
    """t gate applied to qubit."""
    op = _op.t()
    _qubit.apply(op, qubit)


@kernel
def t_adj(qubit: Qubit) -> None:
    """Adjoint t gate applied to qubit."""
    op = _op.t()
    _qubit.apply(_op.adjoint(op), qubit)


@kernel
def p0(qubit: Qubit) -> None:
    """Projector on 0 applied to qubit."""
    op = _op.p0()
    _qubit.apply(op, qubit)


@kernel
def p1(qubit: Qubit) -> None:
    """Projector on 1 applied to qubit."""
    op = _op.p1()
    _qubit.apply(op, qubit)


@kernel
def spin_n(qubit: Qubit) -> None:
    """Spin lowering gate applied to qubit."""
    op = _op.spin_n()
    _qubit.apply(op, qubit)


@kernel
def spin_p(qubit: Qubit) -> None:
    """Spin raising gate applied to qubit."""
    op = _op.spin_p()
    _qubit.apply(op, qubit)


@kernel
def reset(qubit: Qubit) -> None:
    """Reset qubit to 0."""
    op = _op.reset()
    _qubit.apply(op, qubit)


@kernel
def reset_to_one(qubit: Qubit) -> None:
    """Reset qubit to 1."""
    op = _op.reset_to_one()
    _qubit.apply(op, qubit)


@kernel
def cx(control: Qubit, target: Qubit) -> None:
    """Controlled x gate applied to control and target"""
    op = _op.cx()
    _qubit.apply(op, control, target)


@kernel
def cy(control: Qubit, target: Qubit) -> None:
    """Controlled y gate applied to control and target"""
    op = _op.cy()
    _qubit.apply(op, control, target)


@kernel
def cz(control: Qubit, target: Qubit) -> None:
    """Controlled z gate applied to control and target"""
    op = _op.cz()
    _qubit.apply(op, control, target)


@kernel
def ch(control: Qubit, target: Qubit) -> None:
    """Controlled Hadamard gate applied to control and target"""
    op = _op.ch()
    _qubit.apply(op, control, target)


@kernel
def u(theta: float, phi: float, lam: float, qubit: Qubit) -> None:
    """3D rotation gate applied to control and target"""
    op = _op.u(theta, phi, lam)
    _qubit.apply(op, qubit)


@kernel
def rx(theta: float, qubit: Qubit) -> None:
    """Rotation X gate applied to qubit."""
    op = _op.rot(_op.x(), theta)
    _qubit.apply(op, qubit)


@kernel
def ry(theta: float, qubit: Qubit) -> None:
    """Rotation Y gate applied to qubit."""
    op = _op.rot(_op.y(), theta)
    _qubit.apply(op, qubit)


@kernel
def rz(theta: float, qubit: Qubit) -> None:
    """Rotation Z gate applied to qubit."""
    op = _op.rot(_op.z(), theta)
    _qubit.apply(op, qubit)
