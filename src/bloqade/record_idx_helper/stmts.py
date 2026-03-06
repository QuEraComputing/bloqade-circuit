from kirin import ir, types
from kirin.decl import info, statement

from bloqade.types import MeasurementResultType

from ._dialect import dialect


@statement(dialect=dialect)
class GetRecIdxFromMeasurement(ir.Statement):
    name = "get_rec_idx_from_measurement"
    traits = frozenset({ir.Pure()})
    measurement: ir.SSAValue = info.argument(type=MeasurementResultType)
    result: ir.ResultValue = info.result(type=types.Int)


@statement(dialect=dialect)
class GetRecIdxFromPredicate(ir.Statement):
    name = "get_rec_idx_from_predicate"
    traits = frozenset({ir.Pure()})
    predicate_result: ir.SSAValue = info.argument(type=types.Bool)
    result: ir.ResultValue = info.result(type=types.Int)
