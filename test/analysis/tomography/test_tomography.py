import numpy as np
import pytest

from bloqade.analysis.tomography import TomographyResult


def test_reconstructs_single_qubit_density_matrix():
    result = TomographyResult(
        {
            "X": np.array([0, 0, 0, 0, 1, 1, 1, 1, 1, 1]),
            "Y": np.array([0, 0, 0, 1, 1, 1, 1, 1, 1, 1]),
            "Z": np.array([0, 0, 0, 0, 0, 0, 0, 0, 1, 1]),
        }
    )

    expected_bloch = {"X": -0.2, "Y": -0.4, "Z": 0.6}
    expected_density_matrix = 0.5 * np.array(
        [[1.6, -0.2 + 0.4j], [-0.2 - 0.4j, 0.4]],
        dtype=np.complex128,
    )

    np.testing.assert_allclose(result.density_matrix, expected_density_matrix)

    reconstructed_bloch = np.array(
        [
            2.0 * result.density_matrix[0, 1].real,
            -2.0 * result.density_matrix[0, 1].imag,
            (result.density_matrix[0, 0] - result.density_matrix[1, 1]).real,
        ]
    )
    np.testing.assert_allclose(reconstructed_bloch, list(expected_bloch.values()))


def test_fidelity_for_pure_target():
    result = TomographyResult(
        {
            "X": np.array([0, 0, 0, 0, 1, 1, 1, 1, 1, 1]),
            "Y": np.array([0, 0, 0, 1, 1, 1, 1, 1, 1, 1]),
            "Z": np.array([0, 0, 0, 0, 0, 0, 0, 0, 1, 1]),
        }
    )
    target = np.ones(3) / np.sqrt(3.0)

    fidelity = result.fidelity_bloch(target)

    measured_bloch = np.array([-0.2, -0.4, 0.6])
    expected_fidelity = 0.5 * (1.0 + measured_bloch @ target)

    assert fidelity == pytest.approx(expected_fidelity)


@pytest.mark.parametrize("missing_basis", ["X", "Y", "Z"])
def test_requires_every_basis(missing_basis):
    shots = {
        "X": np.array([0, 1]),
        "Y": np.array([0, 1]),
        "Z": np.array([0, 1]),
    }
    del shots[missing_basis]

    with pytest.raises(ValueError, match="requires X, Y, and Z keys"):
        TomographyResult(shots)


@pytest.mark.parametrize(
    ("bad_shots", "message"),
    [
        (np.array([]), "cannot be empty"),
        (np.array([[0], [1]]), r"shape \(shots,\)"),
        (np.array([0.0, 0.5, 1.0]), "only zero or one"),
    ],
)
def test_rejects_invalid_shots(bad_shots, message):
    with pytest.raises(ValueError, match=message):
        TomographyResult(
            {
                "X": bad_shots,
                "Y": np.array([0, 1]),
                "Z": np.array([0, 1]),
            }
        )


@pytest.mark.parametrize(
    "target",
    [np.array([1.0, 0.0]), np.array([2.0, 0.0, 0.0]), np.array([np.nan, 0, 0])],
)
def test_rejects_invalid_target_bloch_vectors(target):
    result = TomographyResult(
        {
            "X": np.array([0, 1]),
            "Y": np.array([0, 1]),
            "Z": np.array([0, 1]),
        }
    )

    with pytest.raises(ValueError):
        result.fidelity_bloch(target)
