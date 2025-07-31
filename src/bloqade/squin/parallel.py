from typing import Any, TypeVar

from kirin.dialects import ilist

from bloqade.types import Qubit

from . import op as _op, qubit as _qubit
from .groups import kernel


@kernel
def x(qubits: ilist.IList[Qubit, Any]) -> None:
    """x gate applied to qubits in parallel."""
    op = _op.x()
    _qubit.broadcast(op, qubits)


@kernel
def y(qubits: ilist.IList[Qubit, Any]) -> None:
    """y gate applied to qubits in parallel."""
    op = _op.y()
    _qubit.broadcast(op, qubits)


@kernel
def z(qubits: ilist.IList[Qubit, Any]) -> None:
    """z gate applied to qubits in parallel."""
    op = _op.z()
    _qubit.broadcast(op, qubits)


@kernel
def sqrt_x(qubits: ilist.IList[Qubit, Any]) -> None:
    """Square root x gate applied to qubits in parallel."""
    op = _op.sqrt_x()
    _qubit.broadcast(op, qubits)


@kernel
def sqrt_y(qubits: ilist.IList[Qubit, Any]) -> None:
    """Square root y gate applied to qubits in parallel."""
    op = _op.sqrt_y()
    _qubit.broadcast(op, qubits)


@kernel
def sqrt_z(qubits: ilist.IList[Qubit, Any]) -> None:
    """Square root gate applied to qubits in parallel."""
    op = _op.s()
    _qubit.broadcast(op, qubits)


@kernel
def h(qubits: ilist.IList[Qubit, Any]) -> None:
    """Hadamard gate applied to qubits in parallel."""
    op = _op.h()
    _qubit.broadcast(op, qubits)


@kernel
def s(qubits: ilist.IList[Qubit, Any]) -> None:
    """s gate applied to qubits in parallel."""
    op = _op.s()
    _qubit.broadcast(op, qubits)


@kernel
def t(qubits: ilist.IList[Qubit, Any]) -> None:
    """t gate applied to qubits in parallel."""
    op = _op.t()
    _qubit.broadcast(op, qubits)


@kernel
def p0(qubits: ilist.IList[Qubit, Any]) -> None:
    """Projector on 0 applied to qubits in parallel."""
    op = _op.p0()
    _qubit.broadcast(op, qubits)


@kernel
def p1(qubits: ilist.IList[Qubit, Any]) -> None:
    """Projector on 1 applied to qubits in parallel."""
    op = _op.p1()
    _qubit.broadcast(op, qubits)


@kernel
def spin_n(qubits: ilist.IList[Qubit, Any]) -> None:
    """Spin lowering gate applied to qubits in parallel."""
    op = _op.spin_n()
    _qubit.broadcast(op, qubits)


@kernel
def spin_p(qubits: ilist.IList[Qubit, Any]) -> None:
    """Spin raising gate applied to qubits in parallel."""
    op = _op.spin_p()
    _qubit.broadcast(op, qubits)


@kernel
def reset(qubits: ilist.IList[Qubit, Any]) -> None:
    """Reset qubit to 0."""
    op = _op.reset()
    _qubit.broadcast(op, qubits)


N = TypeVar("N")


@kernel
def cx(controls: ilist.IList[Qubit, N], targets: ilist.IList[Qubit, N]) -> None:
    """Controlled x gate applied to controls and targets in parallel."""
    op = _op.cx()
    _qubit.broadcast(op, controls, targets)


@kernel
def cy(controls: ilist.IList[Qubit, N], targets: ilist.IList[Qubit, N]) -> None:
    """Controlled y gate applied to controls and targets in parallel."""
    op = _op.cy()
    _qubit.broadcast(op, controls, targets)


@kernel
def cz(controls: ilist.IList[Qubit, N], targets: ilist.IList[Qubit, N]) -> None:
    """Controlled z gate applied to controls and targets in parallel."""
    op = _op.cz()
    _qubit.broadcast(op, controls, targets)


@kernel
def ch(controls: ilist.IList[Qubit, N], targets: ilist.IList[Qubit, N]) -> None:
    """Controlled Hadamard gate applied to controls and targets in parallel."""
    op = _op.ch()
    _qubit.broadcast(op, controls, targets)


@kernel
def u(theta: float, phi: float, lam: float, qubits: ilist.IList[Qubit, Any]) -> None:
    """3D rotation gate applied to controls and targets in parallel."""
    op = _op.u(theta, phi, lam)
    _qubit.broadcast(op, qubits)


@kernel
def rx(theta: float, qubits: ilist.IList[Qubit, Any]) -> None:
    """Rotation X gate applied to qubits in parallel."""
    op = _op.rot(_op.x(), theta)
    _qubit.broadcast(op, qubits)


@kernel
def ry(theta: float, qubits: ilist.IList[Qubit, Any]) -> None:
    """Rotation Y gate applied to qubits in parallel."""
    op = _op.rot(_op.y(), theta)
    _qubit.broadcast(op, qubits)


@kernel
def rz(theta: float, qubits: ilist.IList[Qubit, Any]) -> None:
    """Rotation Z gate applied to qubits in parallel."""
    op = _op.rot(_op.z(), theta)
    _qubit.broadcast(op, qubits)


@kernel
def sqrt_x_adj(qubits: ilist.IList[Qubit, Any]) -> None:
    """Adjoint sqrt_x gate applied to qubits in parallel."""
    op = _op.sqrt_x()
    _qubit.broadcast(_op.adjoint(op), qubits)


@kernel
def sqrt_y_adj(qubits: ilist.IList[Qubit, Any]) -> None:
    """Adjoint sqrt_y gate applied to qubits in parallel."""
    op = _op.sqrt_y()
    _qubit.broadcast(_op.adjoint(op), qubits)


@kernel
def sqrt_z_adj(qubits: ilist.IList[Qubit, Any]) -> None:
    """Adjoint square root z gate applied to qubits in parallel."""
    op = _op.s()
    _qubit.broadcast(_op.adjoint(op), qubits)


@kernel
def s_adj(qubits: ilist.IList[Qubit, Any]) -> None:
    """Adjoint s gate applied to qubits in parallel."""
    op = _op.s()
    _qubit.broadcast(_op.adjoint(op), qubits)


@kernel
def t_adj(qubits: ilist.IList[Qubit, Any]) -> None:
    """Adjoint t gate applied to qubits in parallel."""
    op = _op.t()
    _qubit.broadcast(_op.adjoint(op), qubits)
