from typing import TypeVar

from kirin import lowering
from kirin.dialects import ilist

from bloqade.types import Qubit, MeasurementResult

from .stmts import TerminalLogicalMeasurement

Len = TypeVar("Len", bound=int)
CodeN = TypeVar("CodeN", bound=int)


@lowering.wraps(TerminalLogicalMeasurement)
def terminal_measure(
    qubits: ilist.IList[Qubit, Len],
) -> ilist.IList[ilist.IList[MeasurementResult, CodeN], Len]:
    """Perform measurements on a list of logical qubits.

    Measurements are returned as a nested list where each member list
    contains the individual measurement results for the constituent physical qubits per logical qubit.

    Args:
        qubits (IList[Qubit, Len]): The list of logical qubits to measure.

    Returns:
        IList[IList[MeasurementResult, CodeN], Len]: A nested list containing the measurement results,
            where each inner list corresponds to the measurements of the physical qubits that make up each logical qubit.
    """
    ...
