from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist

from bloqade.types import QubitType, MeasurementResultType

from ._dialect import dialect

Len = types.TypeVar("Len", bound=types.Int)
CodeN = types.TypeVar("CodeN", bound=types.Int)


@statement(dialect=dialect)
class TerminalLogicalMeasurement(ir.Statement):
    """Perform measurements on a list of logical qubits.

    Measurements are returned as a nested list where each member list
    contains the individual measurement results for the constituent physical qubits per logical qubit.

    Args:
        qubits (IList[QubitType, Len]): The list of logical qubits

    Returns:
        IList[IList[MeasurementResultType, CodeN], Len]: A nested list containing the measurement results,
            where each inner list corresponds to the measurements of the physical qubits that make up each logical qubit.
    """

    traits = frozenset({lowering.FromPythonCall()})
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, Len])
    result: ir.ResultValue = info.result(
        ilist.IListType[ilist.IListType[MeasurementResultType, types.Any], Len]
    )
