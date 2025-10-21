from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist

from bloqade.types import QubitType, MeasurementResultType

from ._dialect import dialect


@statement(dialect=dialect)
class New(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    result: ir.ResultValue = info.result(QubitType)


Len = types.TypeVar("Len", bound=types.Int)


@statement(dialect=dialect)
class Measure(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, Len])
    result: ir.ResultValue = info.result(ilist.IListType[MeasurementResultType, Len])


@statement(dialect=dialect)
class QubitId(ir.Statement):
    traits = frozenset({lowering.FromPythonCall(), ir.Pure()})
    qubit: ir.SSAValue = info.argument(QubitType)
    result: ir.ResultValue = info.result(types.Int)


@statement(dialect=dialect)
class MeasurementId(ir.Statement):
    traits = frozenset({lowering.FromPythonCall(), ir.Pure()})
    measurement: ir.SSAValue = info.argument(MeasurementResultType)
    result: ir.ResultValue = info.result(types.Int)


@statement(dialect=dialect)
class Reset(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, types.Any])
