"""Single-qubit tomography and fidelity analysis helpers."""

from __future__ import annotations

from typing import TypedDict
from functools import lru_cache
from collections.abc import Sequence

import numpy as np
from scipy.stats import binomtest
from scipy.special import logsumexp


# TODO: separate __init__.py and python code implementations?
class PosteriorFidelitySummary(TypedDict):
    """Posterior fidelity summary without the reconstructed Bloch vector."""

    point: float
    median: float
    low: float
    high: float
    error: float


class FidelitySummary(PosteriorFidelitySummary):
    """Summary statistics for reconstructed single-qubit fidelity."""

    bloch: tuple[float, float, float]


DEFAULT_TARGET_BLOCH = np.ones(3, dtype=np.float64) / np.sqrt(3.0)
_DEFAULT_SIGN = np.array((1.0, 1.0, 1.0), dtype=np.float64)


def _weighted_quantile(
    values: np.ndarray,
    quantiles: Sequence[float],
    weights: np.ndarray,
) -> np.ndarray:
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    cdf = np.cumsum(weights)
    cdf /= cdf[-1]
    return np.interp(np.asarray(quantiles, dtype=np.float64), cdf, values)


def _bures_measure(points: np.ndarray) -> np.ndarray:
    radii_sq = np.sum(points * points, axis=1)
    weights = np.zeros(len(points), dtype=np.float64)
    mask = radii_sq < 1.0
    weights[mask] = 1.0 / (np.pi**2 * np.sqrt(np.maximum(1.0 - radii_sq[mask], 1e-12)))
    return weights


def _grid_axis_points(binary_precision: int) -> int:
    return 2 ** min(9, max(4, int(binary_precision))) + 1


@lru_cache(maxsize=None)
def _grid_axis_values(axis_points: int) -> np.ndarray:
    edges = np.linspace(-1.0, 1.0, axis_points + 1, dtype=np.float64)
    return (edges[:-1] + edges[1:]) / 2.0


def _axis_likelihood_window(
    values: np.ndarray,
    n_i: int,
    k_i: int,
    *,
    binary_precision: int,
    min_points: int = 33,
) -> np.ndarray:
    if n_i <= 0 or len(values) <= min_points:
        return values

    probs = np.clip((1.0 + values) / 2.0, 1e-12, 1.0 - 1e-12)
    log_likelihood = k_i * np.log(probs) + (n_i - k_i) * np.log1p(-probs)
    relative_log_likelihood = log_likelihood - np.max(log_likelihood)
    mask = relative_log_likelihood > -float(binary_precision) * np.log(2.0)

    if np.any(mask) and int(mask.sum()) >= min_points:
        return values[mask]

    center = int(np.argmax(log_likelihood))
    radius = min_points // 2
    start = max(0, center - radius)
    stop = min(len(values), center + radius + 1)
    if stop - start < min_points:
        if start == 0:
            stop = min(len(values), min_points)
        else:
            start = max(0, len(values) - min_points)
    return values[start:stop]


def _downsample_axis(values: np.ndarray, keep: int) -> np.ndarray:
    if len(values) <= keep:
        return values
    indices = np.linspace(0, len(values) - 1, num=keep, dtype=int)
    return values[np.unique(indices)]


def _adaptive_bloch_ball_grid(
    axis_points: int,
    n: np.ndarray,
    k: np.ndarray,
    *,
    binary_precision: int,
    max_grid_points: int,
) -> np.ndarray:
    axis_values = _grid_axis_values(axis_points)
    subsets = [
        _axis_likelihood_window(
            axis_values,
            int(n_i),
            int(k_i),
            binary_precision=binary_precision,
        )
        for n_i, k_i in zip(n, k, strict=True)
    ]

    total_points = len(subsets[0]) * len(subsets[1]) * len(subsets[2])
    if total_points > max_grid_points:
        scale = (total_points / max_grid_points) ** (1.0 / 3.0)
        subsets = [
            _downsample_axis(values, max(33, int(round(len(values) / scale))))
            for values in subsets
        ]

    x, y, z = np.meshgrid(*subsets, indexing="ij")
    points = np.stack([x.ravel(), y.ravel(), z.ravel()], axis=1)
    points = points[np.sum(points * points, axis=1) <= 1.0]
    if len(points):
        return points

    broad_axis = _downsample_axis(axis_values, min(len(axis_values), 113))
    x, y, z = np.meshgrid(broad_axis, broad_axis, broad_axis, indexing="ij")
    broad_points = np.stack([x.ravel(), y.ravel(), z.ravel()], axis=1)
    return broad_points[np.sum(broad_points * broad_points, axis=1) <= 1.0]


def posterior_fidelity_summary(
    n: np.ndarray,
    k: np.ndarray,
    target_bloch: np.ndarray,
    *,
    sign: np.ndarray = _DEFAULT_SIGN,
    binary_precision: int | None = None,
    max_grid_points: int = 1_500_000,
) -> PosteriorFidelitySummary:
    """Estimate fidelity and credible interval from tomography axis counts."""

    if binary_precision is None:
        binary_precision = 9
    else:
        binary_precision = max(4, int(binary_precision))
    axis_points = _grid_axis_points(binary_precision)
    points = _adaptive_bloch_ball_grid(
        axis_points,
        np.asarray(n, dtype=np.int64),
        np.asarray(k, dtype=np.int64),
        binary_precision=binary_precision,
        max_grid_points=max_grid_points,
    )

    probs = np.clip((1.0 + points) / 2.0, 1e-12, 1.0 - 1e-12)
    n_arr = np.asarray(n, dtype=np.int64)
    k_arr = np.asarray(k, dtype=np.int64)
    log_likelihood = (k_arr * np.log(probs) + (n_arr - k_arr) * np.log1p(-probs)).sum(
        axis=1
    )

    prior = _bures_measure(points)
    log_prior = np.full(len(points), -np.inf, dtype=np.float64)
    positive_prior = prior > 0.0
    log_prior[positive_prior] = np.log(prior[positive_prior])

    log_weights = log_likelihood + log_prior
    finite = np.isfinite(log_weights)
    if not np.any(finite):
        return {"point": 0.5, "median": 0.5, "low": 0.5, "high": 0.5, "error": 0.0}

    weights = np.exp(log_weights[finite] - logsumexp(log_weights[finite]))
    corrected_points = points[finite] * np.asarray(sign, dtype=np.float64)
    target = np.asarray(target_bloch, dtype=np.float64)
    fidelities = np.clip(
        0.5 + np.sum(corrected_points * target.reshape(1, 3), axis=1) / 2.0,
        0.0,
        1.0,
    )
    if weights.sum() <= 0.0:
        return {"point": 0.5, "median": 0.5, "low": 0.5, "high": 0.5, "error": 0.0}

    low, median, high = _weighted_quantile(fidelities, [0.16, 0.5, 0.84], weights)
    error = max(median - low, high - median)
    return {
        "point": float(np.average(fidelities, weights=weights)),
        "median": float(median),
        "low": float(low),
        "high": float(high),
        "error": float(error),
    }


def logical_expectation(bits: np.ndarray) -> float:
    """Convert logical 0/1 samples into a Pauli expectation value."""

    if len(bits) == 0:
        return float("nan")
    return float(np.mean(1.0 - 2.0 * np.asarray(bits, dtype=np.float64)))


def expectation_conf_interval(
    zero_count: int,
    one_count: int,
    *,
    confidence: float = 0.95,
    method: str = "wilson",
) -> np.ndarray:
    """Return a binomial confidence interval for a Pauli expectation."""

    n = max(1, int(zero_count) + int(one_count))
    zero_interval = binomtest(int(zero_count), n).proportion_ci(
        confidence,
        method=method,
    )
    return (
        2.0 * np.array([zero_interval.low, zero_interval.high], dtype=np.float64) - 1.0
    )


def expectation_with_error_bar(
    zero_count: int,
    one_count: int,
    *,
    confidence: float = 0.95,
    method: str = "wilson",
) -> tuple[float, float]:
    """Return a Pauli expectation and symmetric error bar."""

    num_shots = max(int(zero_count) + int(one_count), 1)
    exp_val = float((int(zero_count) - int(one_count)) / num_shots)
    exp_interval = expectation_conf_interval(
        zero_count,
        one_count,
        confidence=confidence,
        method=method,
    )
    exp_err = float((exp_interval[1] - exp_interval[0]) / 2.0)
    return exp_val, exp_err


def fidelity_from_counts(
    x_bits: np.ndarray,
    y_bits: np.ndarray,
    z_bits: np.ndarray,
    binary_precision: int | None = None,
    *,
    sign_vector: Sequence[float] = (1.0, 1.0, 1.0),
    target_bloch: np.ndarray = DEFAULT_TARGET_BLOCH,
    uncertainty_backend: str = "wilson",
    max_grid_points: int = 1_500_000,
) -> FidelitySummary:
    """Compute a single-qubit fidelity summary from X/Y/Z logical bit arrays."""

    x_zero = int(np.sum(np.asarray(x_bits) == 0))
    x_one = int(np.sum(np.asarray(x_bits) != 0))
    y_zero = int(np.sum(np.asarray(y_bits) == 0))
    y_one = int(np.sum(np.asarray(y_bits) != 0))
    z_zero = int(np.sum(np.asarray(z_bits) == 0))
    z_one = int(np.sum(np.asarray(z_bits) != 0))

    return fidelity_from_zero_one_counts(
        x_zero,
        x_one,
        y_zero,
        y_one,
        z_zero,
        z_one,
        binary_precision,
        sign_vector=sign_vector,
        target_bloch=target_bloch,
        uncertainty_backend=uncertainty_backend,
        max_grid_points=max_grid_points,
    )


def fidelity_from_zero_one_counts(
    x_zero: int,
    x_one: int,
    y_zero: int,
    y_one: int,
    z_zero: int,
    z_one: int,
    binary_precision: int | None = None,
    *,
    sign_vector: Sequence[float] = (1.0, 1.0, 1.0),
    target_bloch: np.ndarray = DEFAULT_TARGET_BLOCH,
    uncertainty_backend: str = "wilson",
    max_grid_points: int = 1_500_000,
) -> FidelitySummary:
    """Compute a single-qubit fidelity summary from X/Y/Z zero/one counts."""

    sign = np.asarray(sign_vector, dtype=np.float64)
    target = np.asarray(target_bloch, dtype=np.float64)

    ex, ex_err = expectation_with_error_bar(x_zero, x_one)
    ey, ey_err = expectation_with_error_bar(y_zero, y_one)
    ez, ez_err = expectation_with_error_bar(z_zero, z_one)

    bloch = np.array([ex, ey, ez], dtype=np.float64) * sign
    point = 0.5 + float(np.dot(bloch, target)) / 2.0
    if uncertainty_backend == "wilson":
        fidelity_err = 0.5 * float(
            np.sqrt(
                np.sum(
                    (target * np.array([ex_err, ey_err, ez_err], dtype=np.float64)) ** 2
                )
            )
        )
        low = point - fidelity_err
        high = point + fidelity_err
        median = point
    elif uncertainty_backend == "bayesian_bloch_ball":
        posterior = posterior_fidelity_summary(
            np.array([x_zero + x_one, y_zero + y_one, z_zero + z_one], dtype=np.int64),
            np.array([x_zero, y_zero, z_zero], dtype=np.int64),
            target,
            sign=sign,
            binary_precision=binary_precision,
            max_grid_points=max_grid_points,
        )
        low = posterior["low"]
        high = posterior["high"]
        fidelity_err = posterior["error"]
        median = posterior["median"]
    else:
        raise ValueError(
            "uncertainty_backend must be 'wilson' or 'bayesian_bloch_ball'."
        )

    return {
        "point": float(point),
        "median": float(median),
        "low": float(low),
        "high": float(high),
        "error": float(fidelity_err),
        "bloch": (float(bloch[0]), float(bloch[1]), float(bloch[2])),
    }


__all__ = [
    "DEFAULT_TARGET_BLOCH",
    "FidelitySummary",
    "PosteriorFidelitySummary",
    "expectation_conf_interval",
    "expectation_with_error_bar",
    "fidelity_from_counts",
    "fidelity_from_zero_one_counts",
    "logical_expectation",
    "posterior_fidelity_summary",
]
