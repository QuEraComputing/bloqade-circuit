import typing

import numpy as np
from kirin import ir

from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.analysis.measure_id import MeasurementIDAnalysis, lattice

T = typing.TypeVar("T")


def _has_no_none(value: tuple[T | None, ...]) -> typing.TypeGuard[tuple[T, ...]]:
    return all(v is not None for v in value)


def _post_processing_function(
    value: lattice.MeasureId,
) -> typing.Callable[[typing.Sequence[bool]], typing.Any] | None:
    if isinstance(value, lattice.RawMeasureId):

        def _measure_func(measurements: typing.Sequence[bool]):
            return measurements[value.idx]

        return _measure_func
    elif isinstance(value, (lattice.DetectorId, lattice.ObservableId)):
        measurement_func = _post_processing_function(value.data)
        if measurement_func is None:
            return None

        def _xor_func(measurements: typing.Sequence[bool]):
            measurements = measurement_func(measurements)
            return bool(np.logical_xor.reduce(measurements, axis=0))

        return _xor_func
    elif isinstance(value, lattice.MeasureIdTuple):
        funcs = tuple(_post_processing_function(v) for v in value.data)
        if not _has_no_none(funcs):
            return None

        def _tuple_func(measurements: typing.Sequence[bool]):
            return value.obj_type([f(measurements) for f in funcs])

        return _tuple_func
    else:
        return None


Params = typing.ParamSpec("Params")
ReturnType = typing.TypeVar("ReturnType")


def generate_post_processing(mt: ir.Method[Params, ReturnType]):
    """Generate a post-processing function to extract user-level values from the raw measurement results.


    Args:
        mt (ir.Method[Params, ReturnType]): The entry point of the program

    Returns:
        (typing.Callable[[ndarray], ReturnType] | None): A function that takes in a 2D numpy array
        of raw measurement results and yields user-level results. The input array shape is
        (n_measurements, n_shots), where each row corresponds to a measurement result and each
        column corresponds to a shot. The output is an iterator over user-level results for
        each shot. If the user-level results cannot be determined, returns None.

    """
    mt_copy = mt.similar()
    AggressiveUnroll(mt_copy.dialects).fixpoint(mt_copy)

    _, user_output = MeasurementIDAnalysis(mt_copy.dialects).run(mt_copy)
    func = typing.cast(
        typing.Callable[[np.ndarray], ReturnType],
        _post_processing_function(user_output),
    )
    if func is None:
        return None

    def _generate_user_results(measurements: np.ndarray):
        """A generator that yields user-level results from raw measurement results.

        Args:
            measurements (np.ndarray): A 2D numpy array of raw measurement results with shape
            (n_measurements, n_shots).

        Yields:
            User-level results for each shot.

        """
        yield from map(func, measurements.T[:])

    return _generate_user_results
