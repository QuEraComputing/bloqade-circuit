"""Check qasm2 gates in the PyQrack backend against gate identities that hold exactly."""

import math

import numpy as np
import pytest

from bloqade import qasm2
from bloqade.pyqrack import StackMemorySimulator

# arbitrary single-qubit input states, prepared with u(theta, phi, lam)
INPUTS = [
    (0.0, 0.0, 0.0),
    (math.pi, 0.0, 0.0),
    (math.pi / 2, 0.0, 0.0),
    (math.pi / 2, math.pi / 2, 0.0),
    (1.1, 0.4, -0.7),
]


def run(kernel, *args):
    return np.asarray(StackMemorySimulator(min_qubits=2).state_vector(kernel, args))


def assert_same_state(a, b):
    # equal up to a global phase
    assert abs(np.vdot(a, b)) == pytest.approx(1.0, abs=1e-6)


@qasm2.extended
def sx_sxdg(theta: float, phi: float, lam: float):
    q = qasm2.qreg(1)
    qasm2.u(q[0], theta, phi, lam)
    qasm2.sx(q[0])
    qasm2.sxdg(q[0])


@qasm2.extended
def sxdg_sx(theta: float, phi: float, lam: float):
    q = qasm2.qreg(1)
    qasm2.u(q[0], theta, phi, lam)
    qasm2.sxdg(q[0])
    qasm2.sx(q[0])


@qasm2.extended
def prep_only(theta: float, phi: float, lam: float):
    q = qasm2.qreg(1)
    qasm2.u(q[0], theta, phi, lam)


@pytest.mark.parametrize("prep", INPUTS)
@pytest.mark.parametrize("kernel", [sx_sxdg, sxdg_sx])
def test_sx_sxdg_is_identity(kernel, prep):
    assert_same_state(run(kernel, *prep), run(prep_only, *prep))


@qasm2.extended
def sx_sx(theta: float, phi: float, lam: float):
    q = qasm2.qreg(1)
    qasm2.u(q[0], theta, phi, lam)
    qasm2.sx(q[0])
    qasm2.sx(q[0])


@qasm2.extended
def x_only(theta: float, phi: float, lam: float):
    q = qasm2.qreg(1)
    qasm2.u(q[0], theta, phi, lam)
    qasm2.x(q[0])


@pytest.mark.parametrize("prep", INPUTS)
def test_sx_squared_is_x(prep):
    assert_same_state(run(sx_sx, *prep), run(x_only, *prep))


@qasm2.extended
def sx_only(theta: float, phi: float, lam: float):
    q = qasm2.qreg(1)
    qasm2.u(q[0], theta, phi, lam)
    qasm2.sx(q[0])


@qasm2.extended
def rx_plus(theta: float, phi: float, lam: float):
    q = qasm2.qreg(1)
    qasm2.u(q[0], theta, phi, lam)
    qasm2.rx(q[0], math.pi / 2)


@qasm2.extended
def sxdg_only(theta: float, phi: float, lam: float):
    q = qasm2.qreg(1)
    qasm2.u(q[0], theta, phi, lam)
    qasm2.sxdg(q[0])


@qasm2.extended
def rx_minus(theta: float, phi: float, lam: float):
    q = qasm2.qreg(1)
    qasm2.u(q[0], theta, phi, lam)
    qasm2.rx(q[0], -math.pi / 2)


@pytest.mark.parametrize("prep", INPUTS)
def test_sx_is_rx_half_pi(prep):
    # sqrt(X) = exp(i pi/4) RX(pi/2); sqrt(X)^dag = exp(-i pi/4) RX(-pi/2)
    assert_same_state(run(sx_only, *prep), run(rx_plus, *prep))
    assert_same_state(run(sxdg_only, *prep), run(rx_minus, *prep))


@qasm2.extended
def csx_csx(theta: float, phi: float, lam: float):
    q = qasm2.qreg(2)
    qasm2.h(q[0])
    qasm2.u(q[1], theta, phi, lam)
    qasm2.csx(q[0], q[1])
    qasm2.csx(q[0], q[1])


@qasm2.extended
def cx_only(theta: float, phi: float, lam: float):
    q = qasm2.qreg(2)
    qasm2.h(q[0])
    qasm2.u(q[1], theta, phi, lam)
    qasm2.cx(q[0], q[1])


@pytest.mark.parametrize("prep", INPUTS)
def test_csx_squared_is_cx(prep):
    # control in |+> makes the relative phase between control branches observable
    assert_same_state(run(csx_csx, *prep), run(cx_only, *prep))


@qasm2.extended
def csx_only(theta: float, phi: float, lam: float):
    q = qasm2.qreg(2)
    qasm2.h(q[0])
    qasm2.u(q[1], theta, phi, lam)
    qasm2.csx(q[0], q[1])


@qasm2.extended
def controlled_s_conjugated_by_h(theta: float, phi: float, lam: float):
    q = qasm2.qreg(2)
    qasm2.h(q[0])
    qasm2.u(q[1], theta, phi, lam)
    qasm2.h(q[1])
    qasm2.cu1(q[0], q[1], math.pi / 2)
    qasm2.h(q[1])


@pytest.mark.parametrize("prep", INPUTS)
def test_csx_is_controlled_hsh(prep):
    # sqrt(X) = H S H exactly, so CSX = H_t CS H_t, with CS = cu1(pi/2)
    assert_same_state(run(csx_only, *prep), run(controlled_s_conjugated_by_h, *prep))


@qasm2.extended
def rz_each(theta: float):
    q = qasm2.qreg(2)
    qasm2.h(q[0])
    qasm2.h(q[1])
    qasm2.rz(q[0], theta)
    qasm2.rz(q[1], theta)


@qasm2.extended
def rz_parallel(theta: float):
    q = qasm2.qreg(2)
    qasm2.h(q[0])
    qasm2.h(q[1])
    qasm2.parallel.rz([q[0], q[1]], theta)


@pytest.mark.parametrize("theta", [0.3, 0.7, math.pi / 2, -1.9])
def test_parallel_rz_matches_rz(theta):
    assert_same_state(run(rz_parallel, theta), run(rz_each, theta))
