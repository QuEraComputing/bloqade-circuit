from kirin import ir, types
from kirin.decl import info, statement

from .._dialect import dialect
from ...stim_statement import StimStatement
from ...auxiliary.types import PauliStringType


@statement(dialect=dialect)
class PPMeasurement(StimStatement):
    name = "MPP"
    p: ir.SSAValue = info.argument(types.Float)
    """probability of noise introduced by measurement. For example 0.01 means 1% the measurement will be flipped"""
    targets: tuple[ir.SSAValue, ...] = info.argument(PauliStringType)
