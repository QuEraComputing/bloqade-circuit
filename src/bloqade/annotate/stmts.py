from kirin import ir, types as kirin_types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist

from bloqade.types import MeasurementResultType
from bloqade.annotate.types import DetectorType, ObservableType

from ._dialect import dialect


@statement
class ConsumesMeasurementResults(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    measurements: ir.SSAValue = info.argument(
        ilist.IListType[MeasurementResultType, kirin_types.Any]
    )


@statement(dialect=dialect)
class SetDetector(ConsumesMeasurementResults):
    coordinates: ir.SSAValue = info.argument(
        type=ilist.IListType[kirin_types.Int | kirin_types.Float, kirin_types.Any]
    )
    result: ir.ResultValue = info.result(DetectorType)


@statement(dialect=dialect)
class SetObservable(ConsumesMeasurementResults):
    result: ir.ResultValue = info.result(ObservableType)
