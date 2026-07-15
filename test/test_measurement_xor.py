"""Lost-aware XOR on measurement outcomes."""

import pytest

from bloqade.types import MeasurementResult, MeasurementResultValue

Zero = MeasurementResultValue.Zero
One = MeasurementResultValue.One
Lost = MeasurementResultValue.Lost


@pytest.mark.parametrize(
    ("lhs", "rhs", "expected"),
    [
        (Zero, Zero, Zero),
        (Zero, One, One),
        (One, Zero, One),
        (One, One, Zero),
        (Lost, Zero, Lost),
        (Lost, One, Lost),
        (Zero, Lost, Lost),
        (One, Lost, Lost),
        (Lost, Lost, Lost),
    ],
)
def test_measurement_value_xor(lhs, rhs, expected):
    assert lhs ^ rhs is expected


@pytest.mark.parametrize(
    ("lhs", "rhs", "expected"),
    [
        (Zero, Zero, Zero),
        (Zero, One, One),
        (One, One, Zero),
        (Lost, One, Lost),
        (One, Lost, Lost),
    ],
)
def test_measurement_result_xor(lhs, rhs, expected):
    result = MeasurementResult(lhs) ^ MeasurementResult(rhs)
    assert isinstance(result, MeasurementResult)
    assert result.value is expected


def test_mixed_measurement_result_and_value_xor():
    assert MeasurementResult(One) ^ Zero == MeasurementResult(One)
    assert One ^ MeasurementResult(One) is Zero
    assert MeasurementResult(Lost) ^ One == MeasurementResult(Lost)
    assert Lost ^ MeasurementResult(Zero) is Lost


def test_measurement_result_xor_rejects_unrelated_types():
    with pytest.raises(TypeError):
        MeasurementResult(Zero) ^ 1
    with pytest.raises(TypeError):
        MeasurementResult(Zero) ^ "0"
