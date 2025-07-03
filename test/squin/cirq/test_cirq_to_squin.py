import math

import cirq
import pytest
from kirin import types
from kirin.passes import inline
from kirin.dialects import ilist

from bloqade import squin
from bloqade.pyqrack import DynamicMemorySimulator
from bloqade.squin.noise.rewrite import RewriteNoiseStmts

rewrite_noise_pass = RewriteNoiseStmts(squin.kernel)


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
        cirq.generalized_amplitude_damp(p=0.1, gamma=0.05).on(q),
        cirq.measure(q),
    )


def nested_circuit():
    q = cirq.LineQubit.range(3)

    return cirq.Circuit(
        cirq.H(q[0]),
        cirq.CircuitOperation(
            cirq.Circuit(cirq.H(q[1]), cirq.CX(q[1], q[2])).freeze(),
            use_repetition_ids=False,
        ).controlled_by(q[0]),
        cirq.measure(*q),
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
        noise_channels,
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

    rewrite_noise_pass(kernel)

    # make sure we produce a valid kernel by running it
    sim = DynamicMemorySimulator()
    ket = sim.state_vector(kernel=kernel)
    print(ket)


def test_return_register():
    circuit = basic_circuit()
    kernel = squin.load_circuit(circuit, return_register=True)
    kernel.print()

    assert isinstance(kernel.return_type, types.Generic)
    assert kernel.return_type.body.is_subseteq(ilist.IListType)


@pytest.mark.xfail
def test_nested_circuit():
    # TODO: lowering for CircuitOperation
    test_circuit(nested_circuit)


def test_passing_in_register():
    circuit = pow_gate_circuit()
    print(circuit)
    kernel = squin.cirq.load_circuit(circuit, register_as_argument=True)
    kernel.print()


def test_passing_and_returning_register():
    circuit = pow_gate_circuit()
    print(circuit)
    kernel = squin.cirq.load_circuit(
        circuit, register_as_argument=True, return_register=True
    )
    kernel.print()


def test_nesting_lowered_circuit():
    q = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(cirq.H(q[0]), cirq.CX(*q))

    get_entangled_qubits = squin.cirq.load_circuit(
        circuit, return_register=True, kernel_name="get_entangled_qubits"
    )
    get_entangled_qubits.print()

    entangle_qubits = squin.cirq.load_circuit(
        circuit, register_as_argument=True, kernel_name="entangle_qubits"
    )

    @squin.kernel
    def main():
        qreg = get_entangled_qubits()
        qreg2 = squin.qubit.new(1)
        entangle_qubits([qreg[1], qreg2[0]])
        return squin.qubit.measure(qreg2)

    # if you get up to here, the validation works
    main.print()

    # inline to see if the IR is correct
    inline.InlinePass(main.dialects)(main)

    main.print()


def test_classical_control(run_sim: bool = False):
    q = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(
        cirq.H(q[0]),
        cirq.measure(q[0]),
        cirq.X(q[1]).with_classical_controls("q(0)"),
        cirq.measure(q[1]),
    )

    print(circuit)

    if run_sim:
        simulator = cirq.Simulator()
        simulator.run(circuit, repetitions=1)

    kernel = squin.cirq.load_circuit(circuit)
    kernel.print()


def test_classical_control_register():
    q = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(
        cirq.H(q[0]),
        cirq.measure(q, key="test"),
        cirq.X(q[1]).with_classical_controls("test"),
        cirq.measure(q[1]),
    )

    print(circuit)

    kernel = squin.cirq.load_circuit(circuit)
    kernel.print()


def test_multiple_classical_controls(run_sim: bool = False):
    q = cirq.LineQubit.range(2)
    q2 = cirq.GridQubit(0, 1)
    circuit = cirq.Circuit(
        cirq.H(q[0]),
        cirq.H(q2),
        cirq.measure(q, key="test"),
        cirq.measure(q2),
        cirq.X(q[1]).with_classical_controls("test", "q(0, 1)"),
        cirq.measure(q[1]),
    )

    print(circuit)

    if run_sim:
        sim = cirq.Simulator()
        sim.run(circuit)

    kernel = squin.cirq.load_circuit(circuit)
    kernel.print()
