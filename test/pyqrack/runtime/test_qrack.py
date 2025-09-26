import math
from unittest.mock import Mock, call

import cirq
import numpy as np
from kirin import ir

from bloqade import qasm2, squin
from pyqrack.pauli import Pauli
from bloqade.pyqrack import StackMemorySimulator
from bloqade.pyqrack.base import MockMemory, PyQrackInterpreter


def run_mock(program: ir.Method, rng_state: Mock | None = None):
    PyQrackInterpreter(
        program.dialects, memory=(memory := MockMemory()), rng_state=rng_state
    ).run(program, ())
    assert isinstance(mock := memory.sim_reg, Mock)
    return mock


def test_basic_gates():
    @qasm2.main
    def program():
        q = qasm2.qreg(3)

        qasm2.h(q[0])
        qasm2.x(q[1])
        qasm2.y(q[2])
        qasm2.z(q[0])
        qasm2.barrier((q[0], q[1]))
        qasm2.id(q[1])
        qasm2.s(q[1])
        qasm2.sdg(q[2])
        qasm2.t(q[0])
        qasm2.tdg(q[1])
        qasm2.sx(q[2])
        qasm2.sxdg(q[0])

    sim_reg = run_mock(program)
    sim_reg.assert_has_calls(
        [
            call.h(0),
            call.x(1),
            call.y(2),
            call.z(0),
            call.s(1),
            call.adjs(2),
            call.t(0),
            call.adjt(1),
            call.u(2, math.pi / 2, math.pi / 2, -math.pi / 2),
            call.u(0, math.pi * (1.5), math.pi / 2, math.pi / 2),
        ]
    )


def test_rotation_gates():
    @qasm2.main
    def program():
        q = qasm2.qreg(3)

        qasm2.rx(q[0], 0.5)
        qasm2.ry(q[1], 0.5)
        qasm2.rz(q[2], 0.5)

    sim_reg = run_mock(program)

    sim_reg.assert_has_calls(
        [
            call.r(Pauli.PauliX, 0.5, 0),
            call.r(Pauli.PauliY, 0.5, 1),
            call.r(Pauli.PauliZ, 0.5, 2),
        ]
    )


def test_u_gates():
    @qasm2.main
    def program():
        q = qasm2.qreg(3)

        qasm2.u(q[0], 0.5, 0.2, 0.1)
        qasm2.u2(q[1], 0.2, 0.1)
        qasm2.u1(q[2], 0.2)

    sim_reg = run_mock(program)
    sim_reg.assert_has_calls(
        [
            call.u(0, 0.5, 0.2, 0.1),
            call.u(1, math.pi / 2, 0.2, 0.1),
            call.u(2, 0, 0, 0.2),
        ]
    )


def test_basic_control_gates():
    @qasm2.main
    def program():
        q = qasm2.qreg(3)

        qasm2.cx(q[0], q[1])
        qasm2.cy(q[1], q[2])
        qasm2.cz(q[2], q[0])
        qasm2.ch(q[0], q[1])
        qasm2.csx(q[1], q[2])
        qasm2.swap(q[0], q[2])  # requires new bloqade version

    sim_reg = run_mock(program)
    sim_reg.assert_has_calls(
        [
            call.mcx([0], 1),
            call.mcy([1], 2),
            call.mcz([2], 0),
            call.mch([0], 1),
            call.mcu([1], 2, math.pi / 2, math.pi / 2, -math.pi / 2),
            call.swap(0, 2),
        ]
    )


def test_special_control():
    @qasm2.main
    def program():
        q = qasm2.qreg(3)

        qasm2.crx(q[0], q[1], 0.5)
        qasm2.cu1(q[1], q[2], 0.5)
        qasm2.cu3(q[2], q[0], 0.5, 0.2, 0.1)
        qasm2.ccx(q[0], q[1], q[2])
        qasm2.cu(q[0], q[1], 0.5, 0.2, 0.1, 0.8)
        qasm2.cswap(q[0], q[1], q[2])

    sim_reg = run_mock(program)
    sim_reg.assert_has_calls(
        [
            call.mcr(Pauli.PauliX, 0.5, [0], 1),
            call.mcu([1], 2, 0, 0, 0.5),
            call.mcu([2], 0, 0.5, 0.2, 0.1),
            call.mcx([0, 1], 2),
            call.u(0, 0.0, 0.0, 0.8),
            call.mcu([0], 1, 0.5, 0.2, 0.1),
            call.cswap([0], 1, 2),
        ]
    )


def test_extended():
    @qasm2.extended
    def program():
        q = qasm2.qreg(4)

        qasm2.parallel.cz(ctrls=[q[0], q[2]], qargs=[q[1], q[3]])
        qasm2.parallel.u([q[0], q[1]], theta=0.5, phi=0.2, lam=0.1)
        qasm2.parallel.rz([q[0], q[1]], 0.5)

    sim_reg = run_mock(program)
    sim_reg.assert_has_calls(
        [
            call.mcz([0], 1),
            call.mcz([2], 3),
            call.u(0, 0.5, 0.2, 0.1),
            call.u(1, 0.5, 0.2, 0.1),
            call.r(3, 0.5, 0),
            call.r(3, 0.5, 1),
        ]
    )


def test_rdm1():
    """
    Is extracting the exact state vector consistent with cirq?
    This test also validates the ordering of the qubit basis.
    """

    @squin.kernel
    def program():
        q = squin.qubit.new(5)
        squin.gate.h(q[1])
        return q

    emulator = StackMemorySimulator(min_qubits=6)
    task = emulator.task(program)
    qubits = task.run()
    rho = emulator.quantum_state(qubits)

    assert all(np.isclose(rho.eigenvalues, [1]))

    circuit = cirq.Circuit()
    qbs = cirq.LineQubit.range(5)
    circuit.append(cirq.H(qbs[1]))
    for i in range(5):
        circuit.append(cirq.I(qbs[i]))
    state = cirq.Simulator().simulate(circuit).state_vector()
    assert cirq.equal_up_to_global_phase(state, rho[1][:, 0])


def test_rdm1b():
    """
    Is extracting the exact state vector consistent with cirq?
    This test also validates the ordering of the qubit basis.
    Same as test_rdm1, but with the total qubits equal to the number of qubits in the program.
    """

    @squin.kernel
    def program():
        q = squin.qubit.new(5)
        squin.gate.h(q[1])
        return q

    emulator = StackMemorySimulator(min_qubits=5)
    task = emulator.task(program)
    qubits = task.run()
    rho = emulator.quantum_state(qubits)

    assert all(np.isclose(rho.eigenvalues, [1]))

    circuit = cirq.Circuit()
    qbs = cirq.LineQubit.range(5)
    circuit.append(cirq.H(qbs[1]))
    for i in range(5):
        circuit.append(cirq.I(qbs[i]))
    state = cirq.Simulator().simulate(circuit).state_vector()
    assert cirq.equal_up_to_global_phase(state, rho[1][:, 0])


def test_rdm2():
    """
    Does the RDM project correctly?
    """

    @squin.kernel
    def program():
        """
        Creates a GHZ state on qubits 0,1,3,4 on a total of 6 qubits.
        """
        q = squin.qubit.new(6)
        squin.gate.h(q[0])
        squin.gate.cx(q[0], q[1])
        squin.gate.cx(q[0], q[3])
        squin.gate.cx(q[0], q[4])
        return q

    emulator = StackMemorySimulator(min_qubits=6)
    task = emulator.task(program)
    qubits = task.run()
    rho = emulator.quantum_state([qubits[x] for x in [0, 1, 3, 4]])
    target = np.array([1] + [0] * (14) + [1]) / np.sqrt(2) + 0j
    assert all(np.isclose(rho.eigenvalues, [1]))
    assert cirq.equal_up_to_global_phase(rho[1][:, 0], target)

    rho2 = emulator.quantum_state([qubits[x] for x in [0, 1, 3]])
    assert all(np.isclose(rho2.eigenvalues, [0.5, 0.5]))
    assert rho2.eigenvectors.shape == (8, 2)


def test_rdm3():
    """
    Out-of-order indexing is consistent with cirq.
    """

    @squin.kernel
    def program():
        """
        Random unitaries on 3 qubits.
        """
        q = squin.qubit.new(3)
        squin.gate.rx(0.1, q[0])
        squin.gate.ry(0.2, q[1])
        squin.gate.rx(0.3, q[2])
        return q

    emulator = StackMemorySimulator(min_qubits=6)
    task = emulator.task(program)
    qubits = task.run()

    # Canonical ordering
    rho = emulator.quantum_state([qubits[x] for x in [0, 1, 2]])
    circuit = cirq.Circuit()
    qbs = cirq.LineQubit.range(3)
    circuit.append(cirq.rx(0.1)(qbs[0]))
    circuit.append(cirq.ry(0.2)(qbs[1]))
    circuit.append(cirq.rx(0.3)(qbs[2]))
    state = cirq.Simulator().simulate(circuit).state_vector()
    assert cirq.equal_up_to_global_phase(state, rho[1][:, 0])

    # Reverse ordering 0->2, 1->, 2->0
    rho = emulator.quantum_state([qubits[x] for x in [2, 1, 0]])
    circuit = cirq.Circuit()
    qbs = cirq.LineQubit.range(3)
    circuit.append(cirq.rx(0.1)(qbs[2]))
    circuit.append(cirq.ry(0.2)(qbs[1]))
    circuit.append(cirq.rx(0.3)(qbs[0]))
    state = cirq.Simulator().simulate(circuit).state_vector()
    assert cirq.equal_up_to_global_phase(state, rho[1][:, 0])

    # Other ordering
    rho = emulator.quantum_state([qubits[x] for x in [1, 2, 0]])
    circuit = cirq.Circuit()
    qbs = cirq.LineQubit.range(3)
    circuit.append(cirq.rx(0.1)(qbs[2]))
    circuit.append(cirq.ry(0.2)(qbs[0]))
    circuit.append(cirq.rx(0.3)(qbs[1]))
    state = cirq.Simulator().simulate(circuit).state_vector()
    assert cirq.equal_up_to_global_phase(state, rho[1][:, 0])


def test_rdm4():
    rho = StackMemorySimulator.quantum_state([])
    assert rho.eigenvalues.shape == (0,)
    assert rho.eigenvectors.shape == (0, 0)


def test_rdm5():
    @squin.kernel
    def program():
        """
        Random unitaries on 3 qubits.
        """
        q = squin.qubit.new(3)
        return q

    emulator = StackMemorySimulator(min_qubits=6)
    task = emulator.task(program)
    qubits = task.run()
    rho = emulator.reduced_density_matrix(qubits)
    assert rho.shape == (8, 8)


def test_rdm_failures():
    @squin.kernel
    def program():
        q = squin.qubit.new(3)
        return q

    emulator = StackMemorySimulator(min_qubits=6)
    task = emulator.task(program)
    qbsA = task.qubits()
    qubits = task.run()
    qubits2 = task.run()
    qbsB = task.qubits()
    assert len(qbsA) == 0
    assert len(qbsB) == 6

    try:
        emulator.quantum_state([qubits[0], qubits[0]])
        assert False, "Should have failed; qubits must be unique"
    except ValueError as e:
        assert str(e) == "Qubits must be unique."

    try:
        emulator.quantum_state([qubits[0], qubits2[1]])
        assert False, "Should have failed; qubits must be from the same register"
    except ValueError as e:
        assert str(e) == "All qubits must be from the same simulator register."


def test_get_qubits():
    @squin.kernel
    def program():
        q = squin.qubit.new(3)
        return q

    emulator = StackMemorySimulator(min_qubits=6)
    task = emulator.task(program)
    task.run()

    qubits2 = task.qubits()
    assert len(qubits2) == 6


def test_batch_run():
    @squin.kernel
    def coinflip():
        qubit = squin.qubit.new(1)[0]
        squin.gate.h(qubit)
        return squin.qubit.measure(qubit)

    emulator = StackMemorySimulator()
    task = emulator.task(coinflip)
    results: dict = task.batch_run(1000)
    assert len(set(results.keys()).symmetric_difference({False, True})) == 0
    assert results[True] + results[False] == 1.0
    assert abs(results[True] - 0.5) < 0.1
    assert abs(results[False] - 0.5) < 0.1


def test_batch_run_IList_converter():
    @squin.kernel
    def coinflip():
        qubit = squin.qubit.new(1)[0]
        squin.gate.h(qubit)
        return [squin.qubit.measure(qubit)]

    emulator = StackMemorySimulator()
    task = emulator.task(coinflip)
    results: dict = task.batch_run(1000)
    assert len(set(results.keys()).symmetric_difference({(False,), (True,)})) == 0


def test_batch_state1():
    """
    Averaging with no selector function
    """

    @squin.kernel
    def coinflip():
        qubit = squin.qubit.new(1)[0]
        squin.gate.h(qubit)
        return squin.qubit.measure(qubit)

    emulator = StackMemorySimulator()
    task = emulator.task(coinflip)
    results = task.batch_state(1000)
    assert results.eigenvalues.shape == (2,)
    assert results.eigenvectors.shape == (2, 2)
    assert np.isclose(sum(results.eigenvalues), 1)
    assert abs(results.eigenvalues[0] - 0.5) < 0.1
    assert abs(results.eigenvalues[1] - 0.5) < 0.1


def test_batch_state2():
    """
    Averaging with a qubit_map function
    """

    @squin.kernel
    def coinflip2():
        qubit = squin.qubit.new(2)
        squin.gate.h(qubit[0])
        bit = squin.qubit.measure(
            qubit[0]
        )  # Other (pythonic) sources of randomness are not possible, so some duct tape is required
        if bit:
            squin.gate.h(qubit[1])
        return qubit[1]

    emulator = StackMemorySimulator(min_qubits=2)
    task = emulator.task(coinflip2)

    results1 = task.batch_state(1000)

    assert results1.eigenvalues.shape == (2,)
    assert results1.eigenvectors.shape == (4, 2)
    assert np.isclose(sum(results1.eigenvalues), 1)
    assert abs(results1.eigenvalues[0] - 0.5) < 0.05
    assert abs(results1.eigenvalues[1] - 0.5) < 0.05

    results2 = task.batch_state(1000, qubit_map=lambda q: [q])

    assert results2.eigenvalues.shape == (2,)
    assert results2.eigenvectors.shape == (2, 2)
    assert np.isclose(sum(results1.eigenvalues), 1)
    assert abs(results2.eigenvalues[0] - 0.85355339) < 0.05
    assert abs(results2.eigenvalues[1] - 0.14644661) < 0.05
