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
            A MeasurementResult can represent both 0 and 1, but also atoms that are lost.
    """
    return _qubit.measure(qubits)


@kernel
def get_qubit_id(qubits: ilist.IList[Qubit, N]) -> ilist.IList[int, N]:
    """Get the global, unique ID of each qubit in the list.

    Args:
        qubits (IList[Qubit, N]): The list of qubits of which you want the ID.

    Returns:
        qubit_ids (IList[int, N]): The list of global, unique IDs of the qubits.
    """
    return _qubit.get_qubit_id(qubits)


@kernel
def get_measurement_id(
    measurements: ilist.IList[MeasurementResult, N],
) -> ilist.IList[int, N]:
    """Get the global, unique ID of each of the measurement results in the list.

    Args:
        measurements (IList[MeasurementResult, N]): The previously taken measurement of which you want to know the ID.
    Returns:
        measurement_ids (IList[int, N]): The list of global, unique IDs of the measurements.
    """
    return _qubit.get_measurement_id(measurements)
