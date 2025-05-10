from kirin import ir, types, lowering
from kirin.decl import info, statement

from .._dialect import dialect
from ...auxiliary.types import PauliStringType


@statement(dialect=dialect)
class PPMeasurement(ir.Statement):
    name = "MPP"
    traits = frozenset({lowering.FromPythonCall()})
    p: ir.SSAValue = info.argument(types.Float)
    """probability of noise introduced by measurement. For example 0.01 means 1% the measurement will be flipped"""
    targets: tuple[ir.SSAValue, ...] = info.argument(PauliStringType)
