from kirin import ir, types
from kirin.decl import info, statement

from .base import SingleQubitGate
from .._dialect import dialect

# Non-Clifford Gates using Stim annotation syntax
# These gates are emitted as annotated gates like:
# - S[T] 0 for T gate
# - I[R_Z(theta=0.3*pi)] 0 for rotation gates
# - I[U3(...)] 0 for general U3 gates
# ---------------------------------------


@statement(dialect=dialect)
class T(SingleQubitGate):
    """T gate represented as S[T] or S_DAG[T] in Stim."""

    name = "T"


@statement(dialect=dialect)
class Rx(SingleQubitGate):
    """Rx rotation gate represented as I[R_X(theta=...)] in Stim."""

    name = "R_X"
    angle: ir.SSAValue = info.argument(types.Float)


@statement(dialect=dialect)
class Ry(SingleQubitGate):
    """Ry rotation gate represented as I[R_Y(theta=...)] in Stim."""

    name = "R_Y"
    angle: ir.SSAValue = info.argument(types.Float)


@statement(dialect=dialect)
class Rz(SingleQubitGate):
    """Rz rotation gate represented as I[R_Z(theta=...)] in Stim."""

    name = "R_Z"
    angle: ir.SSAValue = info.argument(types.Float)


@statement(dialect=dialect)
class U3(SingleQubitGate):
    """U3 gate represented as I[U3(theta=..., phi=..., lambda=...)] in Stim."""

    name = "U3"
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)
    theta: ir.SSAValue = info.argument(types.Float)
    phi: ir.SSAValue = info.argument(types.Float)
    lam: ir.SSAValue = info.argument(types.Float)
