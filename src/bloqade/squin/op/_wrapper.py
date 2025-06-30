from kirin.lowering import wraps

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


@wraps(stmts.Reset)
def reset() -> types.Op: ...


@wraps(stmts.ResetToOne)
def reset_to_one() -> types.Op: ...


@wraps(stmts.Identity)
def identity(*, sites: int) -> types.Op: ...


@wraps(stmts.Rot)
def rot(axis: types.Op, angle: float) -> types.Op: ...


@wraps(stmts.ShiftOp)
def shift(theta: float) -> types.Op: ...


@wraps(stmts.PhaseOp)
def phase(theta: float) -> types.Op: ...


@wraps(stmts.X)
def x() -> types.Op: ...


@wraps(stmts.Y)
def y() -> types.Op: ...


@wraps(stmts.Z)
def z() -> types.Op: ...


@wraps(stmts.SqrtX)
def sqrt_x() -> types.Op: ...


@wraps(stmts.SqrtY)
def sqrt_y() -> types.Op: ...


@wraps(stmts.S)
def sqrt_z() -> types.Op: ...


@wraps(stmts.H)
def h() -> types.Op: ...


@wraps(stmts.S)
def s() -> types.Op: ...


@wraps(stmts.T)
def t() -> types.Op: ...


@wraps(stmts.P0)
def p0() -> types.Op: ...


@wraps(stmts.P1)
def p1() -> types.Op: ...


@wraps(stmts.Sn)
def spin_n() -> types.Op: ...


@wraps(stmts.Sp)
def spin_p() -> types.Op: ...


@wraps(stmts.U3)
def u(theta: float, phi: float, lam: float) -> types.Op: ...


@wraps(stmts.PauliString)
def pauli_string(*, string: str) -> types.Op: ...
