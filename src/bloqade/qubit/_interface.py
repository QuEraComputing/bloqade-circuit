from typing import Any, TypeVar

from kirin.dialects import ilist
from kirin.lowering import wraps

from bloqade.types import Qubit, MeasurementResult

from .stmts import New, IsOne, Reset, IsLost, IsZero, Measure, QubitId, MeasurementId


@wraps(New)
def new() -> Qubit:
    """Create a new qubit.

    Returns:
        Qubit: A new qubit.
    """
    ...


N = TypeVar("N", bound=int)


@wraps(Measure)
def measure(qubits: ilist.IList[Qubit, N]) -> ilist.IList[MeasurementResult, N]:
    """Measure a list of qubits.

    Args:
        qubits (IList[Qubit, N]): The list of qubits to measure.

    Returns:
        IList[MeasurementResult, N]: The list containing the results of the measurements.
            A MeasurementResult can represent both 0 and 1, but also atoms that are lost.
    """
    ...


@wraps(QubitId)
def get_qubit_id(qubits: ilist.IList[Qubit, N]) -> ilist.IList[int, N]: ...


@wraps(MeasurementId)
def get_measurement_id(
    measurements: ilist.IList[MeasurementResult, N],
) -> ilist.IList[int, N]: ...


@wraps(Reset)
def reset(qubits: ilist.IList[Qubit, Any]) -> None: ...


@wraps(IsZero)
def is_zero(
    measurements: ilist.IList[MeasurementResult, N],
) -> ilist.IList[bool, N]: ...


@wraps(IsOne)
def is_one(measurements: ilist.IList[MeasurementResult, N]) -> ilist.IList[bool, N]: ...


@wraps(IsLost)
def is_lost(
    measurements: ilist.IList[MeasurementResult, N],
) -> ilist.IList[bool, N]: ...
