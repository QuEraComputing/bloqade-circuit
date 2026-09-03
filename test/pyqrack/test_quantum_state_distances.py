import math

import numpy as np
import pytest

from bloqade.pyqrack import QuantumState


def state_from_probabilities(probabilities: list[float]) -> QuantumState:
    return QuantumState(
        eigenvalues=np.asarray(probabilities),
        eigenvectors=np.eye(len(probabilities), dtype=complex),
    )


def test_quantum_state_probability_and_distances():
    state = state_from_probabilities([0.75, 0.25])
    other = np.array([0.5, 0.5])

    assert np.allclose(state.probability(), [0.75, 0.25])
    assert state.variation_distance(state_from_probabilities([0.75, 0.25])) == 0.0
    assert state.variation_distance(other) == pytest.approx(0.25)
    assert state.variation_distance(np.array([1, 0])) == pytest.approx(0.25)
    assert state.total_variation_distance(other) == pytest.approx(0.25)
    assert state.cross_entropy(other) == pytest.approx(
        -0.5 * math.log(0.75) - 0.5 * math.log(0.25)
    )
    assert state.kl_divergence(other) == pytest.approx(
        0.5 * math.log(0.5 / 0.75) + 0.5 * math.log(0.5 / 0.25)
    )
    assert state.js_divergence(other) == pytest.approx(
        0.5
        * (
            0.75 * math.log(0.75 / 0.625)
            + 0.25 * math.log(0.25 / 0.375)
            + 0.5 * math.log(0.5 / 0.625)
            + 0.5 * math.log(0.5 / 0.375)
        )
    )
    assert state.bhattacharyya_distance(other) == pytest.approx(
        -math.log(math.sqrt(0.75 * 0.5) + math.sqrt(0.25 * 0.5))
    )


def test_quantum_state_distances_accept_counts_and_bitstring_samples():
    state = state_from_probabilities([0.75, 0.25])

    assert state.js_divergence({"0": 3, "1": 1}) == pytest.approx(0.0)
    assert state.kl_divergence({"0": 3, "1": 1}) == pytest.approx(0.0)
    assert state.variation_distance(["0", "0", "0", "1"]) == pytest.approx(0.0)
    assert state.variation_distance([[0], [0], [0], [1]]) == pytest.approx(0.0)
    assert state.total_variation_distance(
        np.array([[0], [0], [0], [1]])
    ) == pytest.approx(0.0)


def test_divergences_handle_zero_probability_consistently():
    state = state_from_probabilities([1.0, 0.0])
    other = np.array([0.0, 1.0])

    assert math.isinf(state.cross_entropy(other))
    assert math.isinf(state.kl_divergence(other))
    assert state.js_divergence(other) == pytest.approx(math.log(2))
    assert math.isinf(state.bhattacharyya_distance(other))


@pytest.mark.parametrize(
    "distribution",
    [
        np.array([0.2, 0.2]),
        {0: -1, 1: 2},
        np.array([0.5, np.nan]),
    ],
)
def test_distances_reject_invalid_distributions(distribution):
    state = state_from_probabilities([0.5, 0.5])

    with pytest.raises(ValueError):
        state.variation_distance(distribution)
