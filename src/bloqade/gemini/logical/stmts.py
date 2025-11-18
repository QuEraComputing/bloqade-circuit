from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist

from bloqade.types import QubitType, MeasurementResultType

from ._dialect import dialect

Len = types.TypeVar("Len", bound=types.Int)
CodeN = types.TypeVar("CodeN", bound=types.Int)


@statement(dialect=dialect)
class TerminalLogicalMeasurement(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, Len])
    result: ir.ResultValue = info.result(
        ilist.IListType[ilist.IListType[MeasurementResultType, CodeN], Len]
    )
