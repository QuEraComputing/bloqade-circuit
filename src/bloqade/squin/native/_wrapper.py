from kirin import lowering

from .stmts import CZ, R, Rz
from ..op.types import Op


@lowering.wraps(CZ)
def cz(cz: CZ) -> Op:
    """
    Controlled-Z gate.

    Returns:
        Op: The resulting operator.
    """
    ...


@lowering.wraps(R)
def r(
    axis_angle: float,
) -> Op:
    """
    Single qubit rotation gate around an arbitrary axis in the XY plane.

    Args:
        axis_angle: The angle in radians that defines the axis of rotation in the XY plane. 0 is the X axis, π/2 is the Y axis.
        rotation_angle: The angle in radians to rotate around the defined axis.

    Returns:
        Op: The resulting operator.
    """
    ...


@lowering.wraps(Rz)
def rz(rotation_angle: float) -> Op:
    """
    Single qubit rotation around the Z axis.

    Args:
        rotation_angle: The angle in radians to rotate around the Z axis.

    Returns:
        Op: The resulting operator.
    """
    ...
