"""Verify that squin gate instructions implement their expected unitary matrices.

Mirrors test/native/test_matrices.py — uses the Choi/Bell-state trick so the
full unitary is recovered from a single simulation (immune to the simulator's
random global phase). See that file for methodology details.
"""

import math

import numpy as np
import pytest

import stim
from bloqade import squin
from bloqade.pyqrack import DynamicMemorySimulator


def _named(name: str) -> np.ndarray:
    """Reference unitary for a Clifford gate, from stim (little-endian)."""
    return stim.Tableau.from_named_gate(name).to_unitary_matrix(endian="little")


T_MAT = np.array([[1, 0], [0, np.exp(1j * math.pi / 4)]], dtype=complex)
T_ADJ_MAT = np.array([[1, 0], [0, np.exp(-1j * math.pi / 4)]], dtype=complex)


def rx(theta: float) -> np.ndarray:
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return np.array([[c, -1j * s], [-1j * s, c]], dtype=complex)


def ry(theta: float) -> np.ndarray:
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return np.array([[c, -s], [s, c]], dtype=complex)


def rz(theta: float) -> np.ndarray:
    return np.array(
        [[np.exp(-1j * theta / 2), 0], [0, np.exp(1j * theta / 2)]], dtype=complex
    )


def assert_unitary_close(
    U_actual: np.ndarray, U_expected: np.ndarray, atol: float = 1e-6
) -> None:
    idx = np.unravel_index(int(np.argmax(np.abs(U_expected))), U_expected.shape)
    phase = U_actual[idx] / U_expected[idx]
    np.testing.assert_allclose(U_actual, phase * U_expected, atol=atol)


def _run_and_reshape(kernel, n: int) -> np.ndarray:
    sv = np.asarray(DynamicMemorySimulator().state_vector(kernel))
    dim = 2**n
    return math.sqrt(dim) * sv.reshape(dim, dim)


@pytest.mark.parametrize(
    "gate_kernel, expected",
    [
        (squin.x, _named("X")),
        (squin.y, _named("Y")),
        (squin.z, _named("Z")),
        (squin.h, _named("H")),
        (squin.s, _named("S")),
        (squin.s_adj, _named("S_DAG")),
        (squin.t, T_MAT),
        (squin.t_adj, T_ADJ_MAT),
        (squin.sqrt_x, _named("SQRT_X")),
        (squin.sqrt_x_adj, _named("SQRT_X_DAG")),
        (squin.sqrt_y, _named("SQRT_Y")),
        (squin.sqrt_y_adj, _named("SQRT_Y_DAG")),
    ],
)
def test_squin_1q_matrix(gate_kernel, expected):
    @squin.kernel
    def choi():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])
        gate_kernel(q[1])

    U = _run_and_reshape(choi, n=1)
    assert_unitary_close(U, expected)


@pytest.mark.parametrize(
    "gate_kernel, expected_fn",
    [(squin.rx, rx), (squin.ry, ry), (squin.rz, rz)],
)
@pytest.mark.parametrize(
    "angle", (0.0, math.pi / 4, math.pi / 2, math.pi, -math.pi / 3, 1.234)
)
def test_squin_rotation_matrix(gate_kernel, expected_fn, angle):
    @squin.kernel
    def choi():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])
        gate_kernel(angle, q[1])

    U = _run_and_reshape(choi, n=1)
    assert_unitary_close(U, expected_fn(angle))


@pytest.mark.parametrize(
    "theta, phi, lam",
    [
        (0.0, 0.0, 0.0),
        (math.pi / 2, 0.0, 0.0),
        (math.pi, math.pi / 2, -math.pi / 2),
        (0.7, 1.1, -0.3),
    ],
)
def test_squin_u3_matrix(theta, phi, lam):
    @squin.kernel
    def choi():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])
        squin.u3(theta, phi, lam, q[1])

    U = _run_and_reshape(choi, n=1)
    expected = rz(phi) @ ry(theta) @ rz(lam)
    assert_unitary_close(U, expected)


@pytest.mark.parametrize(
    "gate_kernel, expected",
    [
        (squin.cz, _named("CZ")),
        (squin.cx, _named("CNOT")),
        (squin.cy, _named("CY")),
    ],
)
def test_squin_2q_matrix(gate_kernel, expected):
    @squin.kernel
    def choi():
        q = squin.qalloc(4)
        squin.h(q[0])
        squin.h(q[1])
        squin.cx(q[0], q[2])
        squin.cx(q[1], q[3])
        gate_kernel(q[2], q[3])

    U = _run_and_reshape(choi, n=2)
    assert_unitary_close(U, expected)


@pytest.mark.parametrize(
    "angle", (0.0, math.pi / 4, math.pi / 2, math.pi, -math.pi / 3, 1.234)
)
def test_squin_shift_matrix(angle):
    @squin.kernel
    def choi():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])
        squin.shift(angle, q[1])

    U = _run_and_reshape(choi, n=1)
    assert_unitary_close(U, rz(angle))


@pytest.mark.parametrize(
    "x_rad, z_rad, axis_phase_rad",
    [
        (math.pi / 2, 0.0, 0.0),
        (math.pi, 0.0, 0.0),
        (math.pi / 2, 0.0, math.pi / 4),
        (math.pi / 3, math.pi / 5, -math.pi / 7),
        (0.7, 1.1, -0.3),
    ],
)
def test_squin_phased_xz_matrix(x_rad, z_rad, axis_phase_rad):
    @squin.kernel
    def choi():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])
        squin.phased_xz(x_rad, z_rad, axis_phase_rad, q[1])

    U = _run_and_reshape(choi, n=1)
    expected = rz(axis_phase_rad + z_rad) @ rx(x_rad) @ rz(-axis_phase_rad)
    assert_unitary_close(U, expected)
