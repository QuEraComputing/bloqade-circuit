from kirin.dialects import ilist

from bloqade.types import Qubit, MeasurementResult

from . import broadcast
from .._prelude import kernel


@kernel
def reset(qubit: Qubit) -> None:
    """
    Reset a qubit to the zero state.

    Args:
        qubit (Qubit): The list qubit to reset.
    """
    return broadcast.reset(ilist.IList([qubit]))


@kernel
def measure(qubit: Qubit) -> MeasurementResult:
    """Measure a qubit.

    Args:
        qubit (Qubit): The qubit to measure.

    Returns:
        MeasurementResult: The result of the measurement.
            A MeasurementResult can represent both 0 and 1, but also atoms that are lost.
    """
    measurement_results = broadcast.measure(ilist.IList([qubit]))
    return measurement_results[0]


@kernel
def get_qubit_id(qubit: Qubit) -> int:
    """Get the global, unique ID of the qubit.

    Args:
        qubit (Qubit): The qubit of which you want the ID.

    Returns:
        qubit_id (int): The global, unique ID of the qubit.
    """
    ids = broadcast.get_qubit_id(ilist.IList([qubit]))
    return ids[0]


@kernel
def get_measurement_id(measurement: MeasurementResult) -> int:
    """Get the global, unique ID of the measurement result.

    Args:
        measurement (MeasurementResult): The previously taken measurement of which you want to know the ID.
    Returns:
        measurement_id (int): The global, unique ID of the measurement.
    """
    ids = broadcast.get_measurement_id(ilist.IList([measurement]))
    return ids[0]


@kernel
def is_zero(measurement: MeasurementResult) -> bool:
    """Check if the measurement result is equivalent to measuring the zero state.

    Args:
        measurement (MeasurementResult): The measurement result to check.
    Returns:
        bool: True if the measurement result is equivalent to measuring the zero state, False otherwise.

    """
    results = broadcast.is_zero(ilist.IList([measurement]))
    return results[0]


@kernel
def is_one(measurement: MeasurementResult) -> bool:
    """Check if the measurement result is equivalent to measuring the one state.

    Args:
        measurement (MeasurementResult): The measurement result to check.
    Returns:
        bool: True if the measurement result is equivalent to measuring the one state, False otherwise.

    """
    results = broadcast.is_one(ilist.IList([measurement]))
    return results[0]


@kernel
def is_lost(measurement: MeasurementResult) -> bool:
    """Check if the measurement result indicates atom loss.

    Args:
        measurement (MeasurementResult): The measurement result to check.
    Returns:
        bool: True if the measurement result indicates atom loss, False otherwise.
    """
    results = broadcast.is_lost(ilist.IList([measurement]))
    return results[0]
