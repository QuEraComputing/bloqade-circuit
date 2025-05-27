import math

import cirq
import pytest

from bloqade import squin
from bloqade.pyqrack import DynamicMemorySimulator


def basic_circuit():
    qubit = cirq.GridQubit(0, 0)
    qubit2 = cirq.GridQubit(1, 0)

    # Create a circuit.
    return cirq.Circuit(
        cirq.X(qubit),
        cirq.Y(qubit2),
        cirq.Z(qubit),
        cirq.H(qubit),
        cirq.S(qubit),
        cirq.T(qubit2),
        cirq.Rx(rads=math.pi / 4).on(qubit),
        cirq.Ry(rads=math.pi / 3).on(qubit2),
        cirq.Rz(rads=math.pi / 10).on(qubit),
        cirq.CX(qubit2, qubit),
        cirq.CZ(qubit, qubit2),
        cirq.measure(qubit, key="m"),  # Measurement.
    )


def controlled_gates():
    q0 = cirq.NamedQubit("q0")
    q1 = cirq.NamedQubit("q1")

    return cirq.Circuit(
        cirq.H(q1),
        cirq.X(q0).controlled_by(q1),
        cirq.Rx(rads=math.pi / 4).on(q0).controlled_by(q1),
        cirq.measure(q0, q1),
    )


def phased_gates():
    q0 = cirq.LineQubit(0)

    return cirq.Circuit(
        cirq.PhasedXPowGate(phase_exponent=0.1 * math.pi).on(q0),
        cirq.PhasedXZGate(
            x_exponent=0.1 * math.pi,
            z_exponent=0.2 * math.pi,
            axis_phase_exponent=0.3 * math.pi,
        ).on(q0),
        cirq.measure(q0),
    )


def pow_gate_circuit():
    q0 = cirq.LineQubit(0)
    q1 = cirq.LineQubit(1)

    return cirq.Circuit(
        cirq.X(q0) ** 0.5,
        cirq.Y(q1) ** 0.3,
        cirq.measure(q0, q1),
    )


def two_qubit_pow_gates():
    q0 = cirq.LineQubit(0)
    q1 = cirq.LineQubit(1)

    return cirq.Circuit(
        cirq.CX(q0, q1) ** 2, cirq.CZ(q0, q1) ** 0.123, cirq.measure(q0, q1)
    )


def swap_circuit():
    q0 = cirq.LineQubit(0)
    q1 = cirq.LineQubit(1)

    print(cirq.decompose_once(cirq.SWAP(q0, q1)))

    return cirq.Circuit(
        cirq.X(q0),
        cirq.SWAP(q0, q1),
        cirq.ISWAP(q0, q1),
        cirq.measure(q0),  # should always be 1
    )


def parity_gate_circuit():
    q0 = cirq.LineQubit(0)
    q1 = cirq.LineQubit(1)

    return cirq.Circuit(
        cirq.XX(q0, q1), cirq.YY(q0, q1), cirq.ZZ(q0, q1), cirq.measure(q0, q1)
    )


def three_qubit_gates():
    q = [cirq.LineQubit(i) for i in range(3)]

    print(cirq.decompose_once(cirq.CSWAP(*q)))

    return cirq.Circuit(
        cirq.CCX(*q),
        cirq.CCZ(*q),
        cirq.CSWAP(*q),
    )


def noise_channels():
    q = cirq.LineQubit(0)

    return cirq.Circuit(
        cirq.X(q),
        cirq.bit_flip(0.1).on(q),
        cirq.amplitude_damp(0.1).on(q),
        cirq.measure(q),
    )


@pytest.mark.parametrize(
    "circuit_f",
    [
        basic_circuit,
        controlled_gates,
        parity_gate_circuit,
        phased_gates,
        pow_gate_circuit,
        two_qubit_pow_gates,
        swap_circuit,
        three_qubit_gates,
    ],
)
def test_circuit(circuit_f, run_sim: bool = False):
    circuit = circuit_f()

    print("Circuit:")
    print(circuit)

    if run_sim:
        # NOTE: to make sure the circuit is actually valid in cirq
        simulator = cirq.Simulator()
        simulator.run(circuit, repetitions=1)

    kernel = squin.load_circuit(circuit)

    kernel.print()

    # make sure we produce a valid kernel by running it
    sim = DynamicMemorySimulator()
    ket = sim.state_vector(kernel=kernel)
    print(ket)


# test_circuit(noise_channels, run_sim=True)
