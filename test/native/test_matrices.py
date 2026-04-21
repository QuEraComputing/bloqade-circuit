"""Verify that native gate instructions implement their expected unitary matrices.

Each test uses the Choi/Bell-state trick: prepare a maximally entangled state
on (ancilla, target) qubits, apply the gate to the target, then reshape the
resulting state vector to recover the gate's unitary matrix (up to a single
global phase). This is robust to the per-simulation random global phase that
the underlying simulator applies.

Everything is expressed in pyqrack's little-endian convention (state index
s = sum_j q[j] * 2^j), so stim reference matrices are requested with
endian="little" and no basis permutation is needed.
"""

import math

import numpy as np
import pytest

import stim
from bloqade import squin, native
from bloqade.pyqrack import DynamicMemorySimulator
from bloqade.native.stdlib import simple as native_simple


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
    """Assert U_actual == U_expected up to a single global phase."""
    idx = np.unravel_index(int(np.argmax(np.abs(U_expected))), U_expected.shape)
    phase = U_actual[idx] / U_expected[idx]
    np.testing.assert_allclose(U_actual, phase * U_expected, atol=atol)


def _run_and_reshape(kernel, n: int) -> np.ndarray:
    """Simulate kernel and reshape the (2n)-qubit Choi state to an n-qubit unitary."""
    sv = np.asarray(DynamicMemorySimulator().state_vector(kernel))
    dim = 2**n
    return math.sqrt(dim) * sv.reshape(dim, dim)


@pytest.mark.parametrize(
    "gate_kernel, expected",
    [
        (native.x, _named("X")),
        (native.y, _named("Y")),
        (native.z, _named("Z")),
        (native.h, _named("H")),
        (native.s, _named("S")),
        (native.s_dag, _named("S_DAG")),
        (native.t, T_MAT),
        (native_simple.t_adj, T_ADJ_MAT),
        (native.sqrt_x, _named("SQRT_X")),
        (native.sqrt_x_adj, _named("SQRT_X_DAG")),
        (native.sqrt_y, _named("SQRT_Y")),
        (native.sqrt_y_adj, _named("SQRT_Y_DAG")),
    ],
)
def test_native_1q_matrix(gate_kernel, expected):
    @native.kernel
    def choi():
        q = squin.qalloc(2)
        native.h(q[0])
        native.cx(q[0], q[1])
        gate_kernel(q[1])

    U = _run_and_reshape(choi, n=1)
    assert_unitary_close(U, expected)


@pytest.mark.parametrize(
    "gate_kernel, expected_fn",
    [(native.rx, rx), (native.ry, ry), (native.rz, rz)],
)
@pytest.mark.parametrize(
    "angle", (0.0, math.pi / 4, math.pi / 2, math.pi, -math.pi / 3, 1.234)
)
def test_native_rotation_matrix(gate_kernel, expected_fn, angle):
    @native.kernel
    def choi():
        q = squin.qalloc(2)
        native.h(q[0])
        native.cx(q[0], q[1])
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
def test_native_u3_matrix(theta, phi, lam):
    @native.kernel
    def choi():
        q = squin.qalloc(2)
        native.h(q[0])
        native.cx(q[0], q[1])
        native.u3(theta, phi, lam, q[1])

    U = _run_and_reshape(choi, n=1)
    expected = rz(phi) @ ry(theta) @ rz(lam)
    assert_unitary_close(U, expected)


@pytest.mark.parametrize(
    "gate_kernel, expected",
    [
        (native.cz, _named("CZ")),
        (native.cx, _named("CNOT")),
        (native.cy, _named("CY")),
    ],
)
def test_native_2q_matrix(gate_kernel, expected):
    @native.kernel
    def choi():
        q = squin.qalloc(4)
        native.h(q[0])
        native.h(q[1])
        native.cx(q[0], q[2])
        native.cx(q[1], q[3])
        gate_kernel(q[2], q[3])

    U = _run_and_reshape(choi, n=2)
    assert_unitary_close(U, expected)
