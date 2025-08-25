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
def rot(axis: types.Op, angle: float) -> types.Op:
    """Rotation around axis by the specified angle (in radian units), i.e."""
    ...


@wraps(stmts.ShiftOp)
def shift(theta: float) -> types.Op:
    """Phase shift operator, that shifts the phase with the given angle theta (in radian units), i.e.

    $$
    |1\\rangle \\to e^{i\\theta} |1\\rangle
    $$

    while leaving the state $$|0\\rangle$$ unchanged.
    """
    ...


@wraps(stmts.PhaseOp)
def phase(theta: float) -> types.Op:
    """Phase operator, that applies the phase factor with the given angle theta (in radian units), i.e.

    $$
    |\\psi\\rangle \\to e^{i\\theta} |\\psi\\rangle
    $$
    """
    ...


@wraps(stmts.X)
def x() -> types.PauliOp: ...


@wraps(stmts.Y)
def y() -> types.PauliOp: ...


@wraps(stmts.Z)
def z() -> types.PauliOp: ...


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
def u(theta: float, phi: float, lam: float) -> types.Op:
    """The three-axis rotation operator (all angles are given in radian units), defined as

    $$
    U_3(\\theta, \\phi, \\lambda) = R_z(\\phi) R_y(\\theta) R_z(\\lambda)
    $$
    """
    ...


@wraps(stmts.PauliString)
def pauli_string(*, string: str) -> types.PauliStringOp: ...
