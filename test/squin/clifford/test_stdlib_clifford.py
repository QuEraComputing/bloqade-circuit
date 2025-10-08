import math
from typing import Any

import numpy as np
import pytest
from kirin import ir

from bloqade import squin
from bloqade.types import Qubit
from bloqade.pyqrack import StackMemorySimulator, DynamicMemorySimulator


@pytest.mark.parametrize("control_gate", [squin.cx, squin.cy])
def test_ghz(control_gate: ir.Method[[Qubit, Qubit], Any]):
    n = 4

    @squin.kernel
    def main():
        q = squin.qubit.new(n)
        squin.h(q[0])

        for i in range(n - 1):
            control_gate(q[i], q[i + 1])

    main.print()

    sim = StackMemorySimulator(min_qubits=n)
    ket = sim.state_vector(main)

    assert math.isclose(abs(ket[0]) ** 2, 0.5, abs_tol=1e-4)
    assert math.isclose(abs(ket[-1] ** 2), 0.5, abs_tol=1e-4)
    for k in ket[1:-1]:
        assert k == 0


@pytest.mark.parametrize(
    "gate_func, expected",
    [
        (squin.x, [0.0, 1.0]),
        (squin.y, [0.0, 1.0]),
        (squin.z, [1.0, 0.0]),
        (squin.h, [c := 1 / math.sqrt(2.0), c]),
        (squin.t, [1.0, 0.0]),
        (squin.t_adj, [1.0, 0.0]),
        (squin.sqrt_x, [c, -c * 1j]),
        (squin.sqrt_y, [c, -c]),
        (squin.sqrt_x_adj, [c, c * 1j]),
        (squin.sqrt_y_adj, [c, c]),
        (squin.s, [1.0, 0.0]),
        (squin.s_adj, [1.0, 0.0]),
    ],
)
def test_1q_gate(gate_func: ir.Method[[Qubit], None], expected: Any):
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        gate_func(q[0])

    sv = DynamicMemorySimulator().state_vector(main)
    sv = np.asarray(sv)

    if abs(sv[0]) > 1e-10:
        sv /= sv[0] / np.abs(sv[0])
    else:
        sv /= sv[1] / np.abs(sv[1])

    print(sv, expected)
    assert np.allclose(sv, expected, atol=1e-6)


@pytest.mark.parametrize(
    "rotation, expected",
    [(squin.rx, [c, -1j * c]), (squin.ry, [c, c]), (squin.rz, [1.0, 0.0])],
)
def test_1q_rots(rotation: ir.Method[[float, Qubit], None], expected: list):
    angle = np.pi / 2.0

    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        rotation(angle, q[0])

    sv = DynamicMemorySimulator().state_vector(main)
    sv = np.asarray(sv)

    if abs(sv[0]) > 1e-10:
        sv /= sv[0] / np.abs(sv[0])
    else:
        sv /= sv[1] / np.abs(sv[1])

    print(sv, expected)
    assert np.allclose(sv, expected, atol=1e-6)


def test_ghz_with_cz():
    n = 4

    @squin.kernel
    def main():
        q = squin.qubit.new(n)
        squin.h(q[0])

        for i in range(n - 1):
            squin.h(q[i + 1])
            squin.cz(q[i], q[i + 1])
            squin.h(q[i + 1])

    main.print()

    sim = StackMemorySimulator(min_qubits=n)
    ket = sim.state_vector(main)

    assert math.isclose(abs(ket[0]) ** 2, 0.5, abs_tol=1e-4)
    assert math.isclose(abs(ket[-1] ** 2), 0.5, abs_tol=1e-4)
    for k in ket[1:-1]:
        assert k == 0


def test_broadcast():
    @squin.kernel
    def h_broadcast():
        q = squin.qubit.new(4)
        squin.broadcast.h(q)

    sim = StackMemorySimulator(min_qubits=4)
    ket = sim.state_vector(h_broadcast)

    for k in ket:
        assert math.isclose(abs(k) ** 2, 1.0 / 16, abs_tol=1e-4)


def test_rotations():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)

        squin.rot(0.0, math.pi, math.pi / 2.0, q[0])
        squin.shift(math.pi / 2.0, q[0])
        squin.u3(math.pi, math.pi, math.pi / 4.0, q[0])

    sim = StackMemorySimulator(min_qubits=1)
    ket = sim.state_vector(main)

    assert math.isclose(abs(ket[0]) ** 2, 1.0, abs_tol=1e-4)
    for k in ket[1:]:
        assert math.isclose(abs(k) ** 2, 0.0, abs_tol=1e-4)


def test_u3():
    rng = np.random.default_rng(0)
    theta = math.pi * rng.random()
    phi = math.pi * rng.random()
    lam = math.pi * rng.random()

    @squin.kernel
    def u3():
        q = squin.qubit.new(1)
        squin.u3(theta, phi, lam, q[0])

        # NOTE: adjoint(U3(theta, phi, lam)) == U3(-theta, -lam, -phi)
        squin.u3(-theta, -lam, -phi, q[0])

    sim = StackMemorySimulator(min_qubits=1)
    ket = sim.state_vector(u3)
    assert math.isclose(abs(ket[0]) ** 2, 1.0, abs_tol=1e-3)
    for k in ket[1:]:
        assert math.isclose(abs(k) ** 2, 0.0, abs_tol=1e-3)

    @squin.kernel
    def u3_decomposed(theta: float, phi: float, lam: float, q: Qubit):
        squin.rz(lam, q)
        squin.ry(theta, q)
        squin.rz(phi, q)

    @squin.kernel
    def u3_decomp_test():
        q = squin.qubit.new(1)
        u3_decomposed(theta, phi, lam, q[0])

        # NOTE: adjoint(U3(theta, phi, lam)) == U3(-theta, -lam, -phi)
        squin.u3(-theta, -lam, -phi, q[0])

    sim = StackMemorySimulator(min_qubits=1)
    ket = sim.state_vector(u3_decomp_test)
    assert math.isclose(abs(ket[0]) ** 2, 1.0, abs_tol=1e-3)
    for k in ket[1:]:
        assert math.isclose(abs(k) ** 2, 0.0, abs_tol=1e-3)
