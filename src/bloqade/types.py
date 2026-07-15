"""Bloqade types.

This module defines the basic types used in Bloqade eDSLs.
"""

from abc import ABC
from typing import Any

from kirin import types
from kirin.dialects.ilist import IList

from bloqade.decoders.dialects.annotate.types import (
    MeasurementResult as MeasurementResult,
    MeasurementResultType as MeasurementResultType,
    MeasurementResultValue as MeasurementResultValue,
)


def _as_measurement_value(
    other: Any,
) -> MeasurementResultValue | None:
    if isinstance(other, MeasurementResult):
        return other.value
    if isinstance(other, MeasurementResultValue):
        return other
    return None


def _xor_measurement_values(
    lhs: MeasurementResultValue, rhs: MeasurementResultValue
) -> MeasurementResultValue:
    if lhs is MeasurementResultValue.Lost or rhs is MeasurementResultValue.Lost:
        return MeasurementResultValue.Lost
    return MeasurementResultValue(int(lhs) ^ int(rhs))


def _measurement_value_xor(
    self: MeasurementResultValue, other: Any
) -> MeasurementResultValue:
    rhs = _as_measurement_value(other)
    if rhs is None:
        return NotImplemented
    return _xor_measurement_values(self, rhs)


def _measurement_value_rxor(
    self: MeasurementResultValue, other: Any
) -> MeasurementResultValue:
    lhs = _as_measurement_value(other)
    if lhs is None:
        return NotImplemented
    return _xor_measurement_values(lhs, self)


def _measurement_result_xor(self: MeasurementResult, other: Any) -> MeasurementResult:
    rhs = _as_measurement_value(other)
    if rhs is None:
        return NotImplemented
    return MeasurementResult(_xor_measurement_values(self.value, rhs))


def _measurement_result_rxor(self: MeasurementResult, other: Any) -> MeasurementResult:
    lhs = _as_measurement_value(other)
    if lhs is None:
        return NotImplemented
    return MeasurementResult(_xor_measurement_values(lhs, self.value))


MeasurementResultValue.__xor__ = _measurement_value_xor  # type: ignore[method-assign]
MeasurementResultValue.__rxor__ = _measurement_value_rxor  # type: ignore[method-assign]
MeasurementResult.__xor__ = _measurement_result_xor  # type: ignore[method-assign]
MeasurementResult.__rxor__ = _measurement_result_rxor  # type: ignore[method-assign]


class Qubit(ABC):
    """Runtime representation of a qubit.

    Note:
        This is the base class of more specific qubit types, such as
        a reference to a piece of quantum register in some quantum register
        dialects.
    """

    pass


Register = IList[Qubit, Any]
"""Runtime representation of a qubit register."""

QubitType = types.PyClass(Qubit)
"""Kirin type for a qubit."""
