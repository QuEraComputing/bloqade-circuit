"""Compare direct wire execution with independent circuit and probability definitions."""

import itertools

import cirq
import numpy as np
import pytest
from density_interpreter import ImpossibleOutcome, DensityInterpreter

from bloqade import squin
from bloqade.squin.passes.squin_to_wire import SquinToWire


@squin.kernel
def rotations(angle: float, flag: bool):
    qs = squin.qalloc(2)
    squin.h(qs[0])
    squin.rx(angle, qs[1])
    squin.cx(qs[0], qs[1])
    for _ in range(2):
        squin.rz(0.37, qs[0])
    if flag:
        squin.s_adj(qs[1])
    else:
        squin.ry(-0.29, qs[1])
    squin.swap(qs[0], qs[1])


@pytest.mark.parametrize("angle", [0.0, 0.31, -1.27])
@pytest.mark.parametrize("flag", [False, True])
def test_unitary_states_match_an_independent_cirq_circuit(angle, flag):
    method = SquinToWire().emit(rotations)
    simulator = DensityInterpreter(method.dialects)
    simulator.run(method, angle, flag)
    a, b = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(
        cirq.H(a),
        cirq.rx(angle)(b),
        cirq.CNOT(a, b),
        cirq.rz(0.37)(a),
        cirq.rz(0.37)(a),
        (cirq.S**-1)(b) if flag else cirq.ry(-0.29)(b),
        cirq.SWAP(a, b),
    )
    state = cirq.final_state_vector(circuit, qubit_order=(a, b), dtype=np.complex128)
    np.testing.assert_allclose(simulator.rho, np.outer(state, state.conj()), atol=1e-12)


@squin.kernel
def feed_forward():
    qs = squin.qalloc(2)
    squin.h(qs[0])
    squin.cx(qs[0], qs[1])
    first = squin.measure(qs[0])
    if first:
        squin.x(qs[1])
    return first, squin.measure(qs[1])


def test_measurement_probabilities_include_classical_feed_forward():
    method = SquinToWire().emit(feed_forward)
    distribution = {}
    for outcomes in itertools.product((0, 1), repeat=2):
        simulator = DensityInterpreter(method.dialects, outcomes=outcomes)
        try:
            _, result = simulator.run(method)
        except ImpossibleOutcome:
            continue
        key = tuple(int(bit) for bit in result)
        distribution[key] = distribution.get(key, 0.0) + simulator.probability
    assert distribution == pytest.approx({(0, 0): 0.5, (1, 0): 0.5})


@squin.kernel
def noisy_entanglement(probability: float):
    qs = squin.qalloc(2)
    squin.h(qs[0])
    squin.cx(qs[0], qs[1])
    squin.depolarize(probability, qs[0])


@pytest.mark.parametrize("probability", [0.0, 0.17, 1.0])
def test_noise_channels_match_an_independent_density_simulation(probability):
    method = SquinToWire().emit(noisy_entanglement)
    simulator = DensityInterpreter(method.dialects)
    simulator.run(method, probability)
    a, b = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(cirq.H(a), cirq.CNOT(a, b), cirq.depolarize(probability)(a))
    expected = (
        cirq.DensityMatrixSimulator(dtype=np.complex128)
        .simulate(circuit, qubit_order=(a, b))
        .final_density_matrix
    )
    np.testing.assert_allclose(simulator.rho, expected, atol=1e-12)


@squin.kernel
def reset_entanglement():
    qs = squin.qalloc(2)
    squin.h(qs[0])
    squin.cx(qs[0], qs[1])
    squin.reset(qs[0])


def test_reset_preserves_the_partner_mixed_state():
    method = SquinToWire().emit(reset_entanglement)
    simulator = DensityInterpreter(method.dialects)
    simulator.run(method)
    np.testing.assert_allclose(simulator.rho, np.diag([0.5, 0.5, 0, 0]), atol=1e-12)


@squin.kernel
def noisy_measurement():
    q = squin.qubit.new()
    squin.single_qubit_pauli_channel(0.1, 0.2, 0.3, q)
    return squin.measure(q)


def test_pauli_channel_measurement_probabilities_match_the_channel_definition():
    method = SquinToWire().emit(noisy_measurement)
    distribution = {}
    for outcome in (0, 1):
        simulator = DensityInterpreter(method.dialects, outcomes=(outcome,))
        _, result = simulator.run(method)
        distribution[int(result)] = simulator.probability
    assert distribution == pytest.approx({0: 0.7, 1: 0.3})


@squin.kernel
def flip_at(k: int):
    qs = squin.qalloc(3)
    squin.x(qs[k])


@pytest.mark.parametrize("k", [-1, 3])
def test_the_wire_interpreter_rejects_an_index_outside_the_register(k):
    method = SquinToWire().emit(flip_at)
    with pytest.raises(AssertionError, match="outside the register"):
        DensityInterpreter(method.dialects).run(method, k)
