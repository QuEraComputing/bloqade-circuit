from typing import Any

from kirin.dialects import ilist
from kirin.lowering import wraps

from bloqade.types import MeasurementResult

from .stmts import SetDetector, SetObservable
from .types import Detector, Observable


@wraps(SetDetector)
def set_detector(
    measurements: ilist.IList[MeasurementResult, Any] | list[MeasurementResult],
    coordinates: ilist.IList[float | int, Any] | list[float | int],
) -> Detector: ...


@wraps(SetObservable)
def set_observable(
    measurements: ilist.IList[MeasurementResult, Any] | list[MeasurementResult],
) -> Observable: ...
