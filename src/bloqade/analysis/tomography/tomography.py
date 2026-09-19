"""Minimal single-qubit tomography helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Mapping, Sequence

import numpy as np

BASES = ("X", "Y", "Z")


def _density_matrix_from_bloch(bloch: Mapping[str, float]) -> np.ndarray:
    required_keys = set(BASES)
    if set(bloch) != required_keys:
        raise ValueError("Single-qubit tomography requires X, Y, and Z keys.")

    x = float(bloch["X"])
    y = float(bloch["Y"])
    z = float(bloch["Z"])
    return 0.5 * np.array(
        [[1.0 + z, x - 1j * y], [x + 1j * y, 1.0 - z]],
        dtype=np.complex128,
    )


def _bloch_mapping_from_sequence(
    bloch: np.ndarray | Sequence[float],
) -> dict[str, float]:
    bloch_arr = np.asarray(bloch, dtype=np.float64)
    return {
        "X": float(bloch_arr[0]),
        "Y": float(bloch_arr[1]),
        "Z": float(bloch_arr[2]),
    }


def _validate_single_qubit_bloch_vector(
    bloch: np.ndarray | Sequence[float],
    *,
    tol: float,
) -> dict[str, float]:
    if tol < 0:
        raise ValueError("tol must be non-negative.")
    bloch_arr = np.asarray(bloch, dtype=np.float64)
    if bloch_arr.shape != (3,):
        raise ValueError("bloch must be a length-3 vector.")
    if not np.all(np.isfinite(bloch_arr)):
        raise ValueError("bloch components must be finite.")
    bloch_norm_squared = float(np.dot(bloch_arr, bloch_arr))
    if bloch_norm_squared > 1.0 + tol:
        raise ValueError("Single-qubit Bloch vector must have squared norm <= 1.")
    return _bloch_mapping_from_sequence(bloch_arr)


def _single_qubit_fidelity(
    density_matrix: np.ndarray,
    target_density_matrix: np.ndarray,
) -> float:
    overlap = float(np.real(np.trace(density_matrix @ target_density_matrix)))
    det_product = float(
        np.real(np.linalg.det(density_matrix))
        * np.real(np.linalg.det(target_density_matrix))
    )
    return overlap + 2.0 * math.sqrt(max(det_product, 0.0))


@dataclass(frozen=True, init=False)
class TomographyResult:
    """Point-estimate single-qubit tomography result."""

    density_matrix: np.ndarray

    def __init__(
        self,
        shots_by_basis: Mapping[str, np.ndarray],
    ) -> None:
        """
        Create a tomography result by computing the density matrix from the shots per basis.

        Args:
            shots_by_basis (Mapping[str, np.ndarray]): A mapping of each basis to an array of shots (0/1's) in each basis.
        """
        if set(shots_by_basis) != set(BASES):
            raise ValueError("Single-qubit tomography requires X, Y, and Z keys.")

        bloch: dict[str, float] = {}
        for basis in BASES:
            shots = np.asarray(shots_by_basis[basis])
            if shots.ndim != 1:
                raise ValueError(
                    "TomographyResult expects each basis to have shape (shots,)."
                )
            if shots.size == 0:
                raise ValueError(f"{basis}-basis shots cannot be empty.")
            if not np.all((shots == 0) | (shots == 1)):
                raise ValueError("Tomography shots must contain only zero or one.")

            shots = shots.astype(np.uint8, copy=False)
            prob_meas_one = float(np.mean(shots))
            bloch[basis] = 1.0 - 2.0 * prob_meas_one

        object.__setattr__(self, "density_matrix", _density_matrix_from_bloch(bloch))

    # NOTE: if you want to add more generic methods for fidelity, to density matrices, just define a new method "fidelity_to_density_mat".
    def fidelity_bloch(
        self,
        target_bloch: np.ndarray | Sequence[float],
        tol: float = 1e-10,
    ) -> float:
        """Return the fidelity to a target state from its Bloch vector."""

        target_density_matrix = _density_matrix_from_bloch(
            _validate_single_qubit_bloch_vector(target_bloch, tol=tol)
        )
        return _single_qubit_fidelity(self.density_matrix, target_density_matrix)


__all__ = [
    "TomographyResult",
]
