# ruff: noqa: D103

import numpy as np
import pytest

from bloqade.analysis.tomography import (
    DEFAULT_TARGET_BLOCH,
    fidelity_from_counts,
    expectation_conf_interval,
    expectation_with_error_bar,
    posterior_fidelity_summary,
    fidelity_from_zero_one_counts,
)


def test_fidelity_from_counts_returns_ordered_interval():
    summary = fidelity_from_counts(
        np.array([0, 0, 1, 0], dtype=np.uint8),
        np.array([0, 1, 0, 0], dtype=np.uint8),
        np.array([0, 0, 0, 1], dtype=np.uint8),
        binary_precision=4,
    )

    assert set(summary) >= {"point", "median", "low", "high", "bloch"}
    assert summary["low"] <= summary["median"] <= summary["high"]
    assert len(summary["bloch"]) == 3


def test_fidelity_from_zero_one_counts_matches_array_counts():
    x_bits = np.array([0, 0, 1, 0], dtype=np.uint8)
    y_bits = np.array([1, 1, 0, 1], dtype=np.uint8)
    z_bits = np.array([0, 1, 1, 1], dtype=np.uint8)

    from_arrays = fidelity_from_counts(
        x_bits,
        y_bits,
        z_bits,
        sign_vector=(1.0, -1.0, 1.0),
        target_bloch=np.array([0.0, 1.0, 0.0], dtype=np.float64),
    )
    from_counts = fidelity_from_zero_one_counts(
        3,
        1,
        1,
        3,
        1,
        3,
        sign_vector=(1.0, -1.0, 1.0),
        target_bloch=np.array([0.0, 1.0, 0.0], dtype=np.float64),
    )

    assert from_counts["point"] == pytest.approx(from_arrays["point"])
    assert from_counts["bloch"] == pytest.approx(from_arrays["bloch"])


def test_expectation_helpers_return_ordered_interval_and_error_bar():
    interval = expectation_conf_interval(3, 1)
    expectation, error = expectation_with_error_bar(3, 1)

    assert interval.shape == (2,)
    assert interval[0] <= expectation <= interval[1]
    assert expectation == pytest.approx(0.5)
    assert error == pytest.approx((interval[1] - interval[0]) / 2.0)


def test_posterior_fidelity_summary_returns_ordered_interval():
    summary = posterior_fidelity_summary(
        np.array([8, 8, 8], dtype=np.int64),
        np.array([7, 6, 7], dtype=np.int64),
        DEFAULT_TARGET_BLOCH,
        binary_precision=4,
        max_grid_points=2_000,
    )

    assert np.isfinite(summary["point"])
    assert summary["low"] <= summary["median"] <= summary["high"]
