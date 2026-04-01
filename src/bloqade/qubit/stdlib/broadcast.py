from typing import Any, TypeVar

from kirin.dialects import ilist

from bloqade.types import Qubit, MeasurementResult

from .. import _interface as _qubit
from .._prelude import kernel

N = TypeVar("N", bound=int)


@kernel
def reset(qubits: ilist.IList[Qubit, Any]) -> None:
    """
    Reset a list of qubits to the zero state.

    Args:
        qubits (IList[Qubit, Any]): The list of qubits to reset.
    """
    _qubit.reset(qubits)


@kernel
def measure(qubits: ilist.IList[Qubit, N]) -> ilist.IList[MeasurementResult, N]:
    """Measure a list of qubits.

    Args:
        qubits (IList[Qubit, N]): The list of qubits to measure.

    Returns:
        IList[MeasurementResult, N]: The list containing the results of the measurements.
            A MeasurementResult can represent both 0 and 1 as well as atom loss.
    """
    return _qubit.measure(qubits)


@kernel
def is_zero(measurements: ilist.IList[MeasurementResult, N]) -> ilist.IList[bool, N]:
    """Check if each MeasurementResult in the list is equivalent to measuring the zero state.

    Args:
        measurements (IList[MeasurementResult, N]): The list of measurement results to check.
    Returns:
        IList[bool, N]: A list of booleans indicating whether each MeasurementResult is equivalent to the zero state.
    """
    return _qubit.is_zero(measurements)


@kernel
def is_one(measurements: ilist.IList[MeasurementResult, N]) -> ilist.IList[bool, N]:
    """Check if each MeasurementResult in the list is equivalent to measuring the one state.

    Args:
        measurements (IList[MeasurementResult, N]): The list of measurement results to check.
    Returns:
        IList[bool, N]: A list of booleans indicating whether each MeasurementResult is equivalent to the one state.
    """
    return _qubit.is_one(measurements)


@kernel
def is_lost(measurements: ilist.IList[MeasurementResult, N]) -> ilist.IList[bool, N]:
    """Check if each MeasurementResult in the list indicates atom loss.

    Args:
        measurements (IList[MeasurementResult, N]): The list of measurement results to check.
    Returns:
        IList[bool, N]: A list of booleans indicating whether each MeasurementResult indicates atom loss.
    """
    return _qubit.is_lost(measurements)
