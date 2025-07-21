from typing import Literal, overload

from kirin.dialects import ilist
from kirin.lowering import wraps

from bloqade.types import Qubit

from . import stmts, types


@wraps(stmts.Kron)
def kron(lhs: types.Op, rhs: types.Op) -> types.Op: ...


@wraps(stmts.Mult)
def mult(lhs: types.Op, rhs: types.Op) -> types.Op: ...


@wraps(stmts.Scale)
def scale(op: types.Op, factor: complex) -> types.Op: ...


@wraps(stmts.Adjoint)
def adjoint(op: types.Op) -> types.Op: ...


@wraps(stmts.Control)
def control(op: types.Op, *, n_controls: int) -> types.Op:
    """
    Create a controlled operator.

    Note, that when considering atom loss, the operator will not be applied if
    any of the controls has been lost.

    Args:
        operator: The operator to apply under the control.
        n_controls: The number qubits to be used as control.

    Returns:
        Operator
    """
    ...


@wraps(stmts.Identity)
def identity(*, sites: int) -> types.Op: ...


@wraps(stmts.Rot)
def rot(axis: types.Op, angle: float) -> types.Op: ...


@wraps(stmts.ShiftOp)
def shift(theta: float) -> types.Op: ...


@wraps(stmts.PhaseOp)
def phase(theta: float) -> types.Op: ...


@wraps(stmts.U3)
def u(theta: float, phi: float, lam: float) -> types.Op: ...


@wraps(stmts.PauliString)
def pauli_string(*, string: str) -> types.Op: ...


# NOTE: single-qubit operators that allow short-hand calls start here


@overload
def reset() -> types.Op: ...


@overload
def reset(q: Qubit) -> None: ...


@overload
def reset(q: ilist.IList[Qubit, Literal[1]]) -> None: ...


@wraps(stmts.Reset)
def reset(*arg) -> types.Op | None: ...


@overload
def reset_to_one() -> types.Op: ...


@overload
def reset_to_one(q: Qubit | ilist.IList[Qubit, Literal[1]]) -> None: ...


@wraps(stmts.ResetToOne)
def reset_to_one() -> types.Op | None: ...


@overload
def x(q: Qubit) -> None: ...


@overload
def x(q: ilist.IList[Qubit, Literal[1]]) -> None: ...


@overload
def x() -> types.Op: ...


@wraps(stmts.X)
def x(*arg) -> types.Op | None: ...


@overload
def y(q: Qubit) -> None: ...


@overload
def y(q: ilist.IList[Qubit, Literal[1]]) -> None: ...


@overload
def y() -> types.Op: ...


@wraps(stmts.Y)
def y(*arg) -> types.Op | None: ...


@overload
def z(q: Qubit) -> None: ...


@overload
def z(q: ilist.IList[Qubit, Literal[1]]) -> None: ...


@overload
def z() -> types.Op: ...


@wraps(stmts.Z)
def z(*arg) -> types.Op | None: ...


@overload
def sqrt_x(q: Qubit) -> None: ...


@overload
def sqrt_x(q: ilist.IList[Qubit, Literal[1]]) -> None: ...


@overload
def sqrt_x() -> types.Op: ...


@wraps(stmts.SqrtX)
def sqrt_x(*arg) -> types.Op | None: ...


@overload
def sqrt_y(q: Qubit) -> None: ...


@overload
def sqrt_y(q: ilist.IList[Qubit, Literal[1]]) -> None: ...


@overload
def sqrt_y() -> types.Op: ...


@wraps(stmts.SqrtY)
def sqrt_y(*arg) -> types.Op | None: ...


@overload
def sqrt_z(q: Qubit) -> None: ...


@overload
def sqrt_z(q: ilist.IList[Qubit, Literal[1]]) -> None: ...


@overload
def sqrt_z() -> types.Op: ...


@wraps(stmts.S)
def sqrt_z(*arg) -> types.Op | None: ...


@overload
def h(q: Qubit) -> None: ...


@overload
def h(q: ilist.IList[Qubit, Literal[1]]) -> None: ...


@overload
def h() -> types.Op: ...


@wraps(stmts.H)
def h(*arg) -> types.Op | None: ...


@overload
def s(q: Qubit) -> None: ...


@overload
def s(q: ilist.IList[Qubit, Literal[1]]) -> None: ...


@overload
def s() -> types.Op: ...


@wraps(stmts.S)
def s(*arg) -> types.Op | None: ...


@overload
def t(q: Qubit) -> None: ...


@overload
def t(q: ilist.IList[Qubit, Literal[1]]) -> None: ...


@overload
def t() -> types.Op: ...


@wraps(stmts.T)
def t(*arg) -> types.Op | None: ...


@overload
def p0(q: Qubit) -> None: ...


@overload
def p0(q: ilist.IList[Qubit, Literal[1]]) -> None: ...


@overload
def p0() -> types.Op: ...


@wraps(stmts.P0)
def p0(*arg) -> types.Op | None: ...


@overload
def p1(q: Qubit) -> None: ...


@overload
def p1(q: ilist.IList[Qubit, Literal[1]]) -> None: ...


@overload
def p1() -> types.Op: ...


@wraps(stmts.P1)
def p1(*arg) -> types.Op | None: ...


@overload
def spin_n(q: Qubit) -> None: ...


@overload
def spin_n(q: ilist.IList[Qubit, Literal[1]]) -> None: ...


@overload
def spin_n() -> types.Op: ...


@wraps(stmts.Sn)
def spin_n(*arg) -> types.Op | None: ...


@overload
def spin_p(q: Qubit) -> None: ...


@overload
def spin_p(q: ilist.IList[Qubit, Literal[1]]) -> None: ...


@overload
def spin_p() -> types.Op: ...


@wraps(stmts.Sp)
def spin_p(*arg) -> types.Op | None: ...
