from kirin import ir, types
from kirin.decl import info, statement

from ._dialect import dialect
from ..op.types import OpType
from ..op.traits import Unitary, FixedSites


@statement(dialect=dialect)
class CZ(ir.Statement):
    """
    Controlled-Z gate.
    """

    traits = frozenset({Unitary(), FixedSites(2)})
    result: ir.ResultValue = info.result(OpType)


@statement(dialect=dialect)
class R(ir.Statement):
    """
    Single qubit rotation gate around an arbitrary axis in the XY plane.
    """

    traits = frozenset({Unitary(), FixedSites(1)})
    axis_angle: ir.SSAValue = info.argument(type=types.Float)
    """The angle in radians that defines the axis of rotation in the XY plane. 0 is the X axis, π/2 is the Y axis."""
    rotation_angle: ir.SSAValue = info.argument(type=types.Float)
    """The angle in radians to rotate around the defined axis."""
    result: ir.ResultValue = info.result(OpType)


@statement(dialect=dialect)
class Rz(ir.Statement):
    """
    Single qubit rotation around the Z axis.
    """

    traits = frozenset({Unitary(), FixedSites(1)})
    rotation_angle: ir.SSAValue = info.argument(type=types.Float)
    """The angle in radians to rotate around the Z axis."""
    result: ir.ResultValue = info.result(OpType)
