from math import pi

import numpy as np
import pytest

from bloqade import qasm2
from bloqade.qasm2 import glob
from bloqade.pyqrack import StackMemorySimulator, MeasurementResultValue
from bloqade.analysis import address
from bloqade.qasm2.passes import parallel
from bloqade.qasm2.rewrite import SimpleGreedyMergePolicy, SimpleOptimalMergePolicy


def test_one():

    @qasm2.gate
    def gate(q1: qasm2.Qubit, q2: qasm2.Qubit):
        qasm2.cx(q1, q2)

    @qasm2.extended
    def test():
        q = qasm2.qreg(4)

        theta = 0.1
        phi = 0.2
        lam = 0.3

        qasm2.u(q[1], theta, phi, lam)
        qasm2.u(q[0], 0.4, phi, lam)
        qasm2.u(q[3], theta, phi, lam)
        qasm2.u(q[2], 0.4, phi, lam)

        gate(q[1], q[3])
        qasm2.barrier((q[1], q[2]))
        qasm2.u(q[2], theta, phi, lam)
        glob.u(theta=theta, phi=phi, lam=lam, registers=[q])
        qasm2.u(q[0], theta, phi, lam)

        gate(q[0], q[2])

    parallel.UOpToParallel(test.dialects)(test)
    test.print()

    # add this to raise error if there are broken ssa references
    _, _ = address.AddressAnalysis(test.dialects).run(test)

    # check that there's parallel statements now
    assert any(
        [
            isinstance(stmt, qasm2.dialects.parallel.UGate)
            for stmt in test.callable_region.blocks[0].stmts
        ]
    )


def test_two():

    @qasm2.extended
    def test():
        q = qasm2.qreg(8)
        theta = 0.1
        theta2 = 0.4
        phi = 0.2
        lam = 0.3

        qasm2.rz(q[0], 0.8)
        qasm2.rz(q[1], 0.7)

        qasm2.u(q[1], theta, phi, lam)
        qasm2.u(q[0], theta2, phi, lam)

        qasm2.rz(q[2], 0.6)
        qasm2.rz(q[3], 0.5)

        qasm2.u(q[3], theta, phi, lam)
        qasm2.u(q[2], theta2, phi, lam)

        qasm2.rz(q[4], 0.5)
        qasm2.rz(q[5], 0.6)

        qasm2.u(q[4], theta, phi, lam)
        qasm2.u(q[5], 0.4, phi, lam)

        qasm2.rz(q[6], 0.7)
        qasm2.rz(q[7], 0.8)

    parallel.UOpToParallel(test.dialects, SimpleOptimalMergePolicy)(test)
    test.print()

    # add this to raise error if there are broken ssa references
    _, _ = address.AddressAnalysis(test.dialects).run(test)


def test_three():

    @qasm2.extended
    def test():
        q1 = qasm2.qreg(1)
        qasm2.u(q1[0], 0.1, 0.2, 0.3)

        q2 = qasm2.qreg(1)
        qasm2.u(q2[0], 0.1, 0.2, 0.3)
        qasm2.cz(q2[0], q1[0])

        q3 = qasm2.qreg(1)
        qasm2.u(q3[0], 0.1, 0.2, 0.3)
        qasm2.cz(q3[0], q2[0])

    parallel.UOpToParallel(test.dialects)(test)
    test.print()

    # add this to raise error if there are broken ssa references
    _, _ = address.AddressAnalysis(test.dialects).run(test)


@pytest.mark.parametrize("policy", [SimpleOptimalMergePolicy, SimpleGreedyMergePolicy])
def test_parallel_cz_stays_after_qubit_dependencies(policy):
    @qasm2.extended
    def kernel():
        q = qasm2.qreg(4)
        qasm2.u(q[3], 0.4, 0.8, 1.2)
        qasm2.u(q[0], 0.7, 0.4, 0.5)
        qasm2.cz(q[0], q[1])
        qasm2.u(q[2], 1.3, 0.2, 0.3)
        qasm2.cz(q[2], q[3])

    sim = StackMemorySimulator(min_qubits=4)
    before = sim.state_vector(kernel)
    parallel.UOpToParallel(kernel.dialects, policy)(kernel)
    after = sim.state_vector(kernel)

    assert abs(np.vdot(before, after)) == pytest.approx(1.0)


def test_parallel_gate_stays_after_measurement():
    @qasm2.extended
    def kernel():
        q = qasm2.qreg(3)
        c = qasm2.creg(1)
        qasm2.u(q[1], pi, 0.0, 0.0)
        qasm2.measure(q[0], c[0])
        qasm2.u(q[0], pi, 0.0, 0.0)
        qasm2.u(q[2], pi, 0.0, 0.0)
        return c

    sim = StackMemorySimulator(min_qubits=3)
    assert sim.run(kernel)[0] == MeasurementResultValue.Zero
    parallel.UOpToParallel(kernel.dialects)(kernel)
    assert sim.run(kernel)[0] == MeasurementResultValue.Zero
    assert any(
        isinstance(stmt, qasm2.dialects.parallel.UGate)
        for stmt in kernel.callable_region.blocks[0].stmts
    )


def test_parallel_gate_stays_after_register_measurement():
    @qasm2.extended
    def kernel():
        q = qasm2.qreg(1)
        other = qasm2.qreg(1)
        c = qasm2.creg(1)
        qasm2.u(other[0], pi, 0.0, 0.0)
        qasm2.measure(q, c)
        qasm2.u(q[0], pi, 0.0, 0.0)
        return c

    sim = StackMemorySimulator(min_qubits=2)
    assert sim.run(kernel)[0] == MeasurementResultValue.Zero
    parallel.UOpToParallel(kernel.dialects)(kernel)
    assert sim.run(kernel)[0] == MeasurementResultValue.Zero


def test_parallel_gate_stays_after_conditional_measurement():
    @qasm2.extended
    def kernel(measure: bool):
        q = qasm2.qreg(2)
        c = qasm2.creg(1)
        qasm2.u(q[1], pi, 0.0, 0.0)
        if measure:
            qasm2.measure(q[0], c[0])
        qasm2.u(q[0], pi, 0.0, 0.0)
        return c

    sim = StackMemorySimulator(min_qubits=2)
    assert sim.run(kernel, args=(True,))[0] == MeasurementResultValue.Zero
    parallel.UOpToParallel(kernel.dialects)(kernel)
    assert sim.run(kernel, args=(True,))[0] == MeasurementResultValue.Zero


def test_parallel_gate_stays_after_reset_with_unknown_address():
    @qasm2.extended
    def kernel(index: int):
        q = qasm2.qreg(2)
        c = qasm2.creg(1)
        qasm2.u(q[1], pi, 0.0, 0.0)
        qasm2.reset(q[index])
        qasm2.u(q[0], pi, 0.0, 0.0)
        qasm2.measure(q[0], c[0])
        return c

    sim = StackMemorySimulator(min_qubits=2)
    assert sim.run(kernel, args=(0,))[0] == MeasurementResultValue.One
    parallel.UOpToParallel(kernel.dialects)(kernel)
    assert sim.run(kernel, args=(0,))[0] == MeasurementResultValue.One


def test_parallel_gate_stays_after_reset_of_conditionally_selected_qubit():
    @qasm2.extended
    def kernel(first: bool):
        q = qasm2.qreg(2)
        c = qasm2.creg(1)
        if first:
            target = q[0]
        else:
            target = q[1]
        qasm2.u(q[1], pi, 0.0, 0.0)
        qasm2.reset(target)
        qasm2.u(q[0], pi, 0.0, 0.0)
        qasm2.measure(q[0], c[0])
        return c

    parallel.UOpToParallel(kernel.dialects)(kernel)
    sim = StackMemorySimulator(min_qubits=2)
    assert sim.run(kernel, args=(True,))[0] == MeasurementResultValue.One


def test_parallel_gate_stays_after_reset_in_closure():
    @qasm2.extended
    def kernel():
        q = qasm2.qreg(2)
        c = qasm2.creg(1)

        def reset_target():
            qasm2.reset(q[0])

        qasm2.u(q[1], pi, 0.0, 0.0)
        reset_target()
        qasm2.u(q[0], pi, 0.0, 0.0)
        qasm2.measure(q[0], c[0])
        return c

    parallel.UOpToParallel(kernel.dialects)(kernel)
    sim = StackMemorySimulator(min_qubits=2)
    assert sim.run(kernel)[0] == MeasurementResultValue.One


def test_merge_with_existing_parallel_gate_after_global_gate():
    @qasm2.extended
    def kernel():
        q = qasm2.qreg(1)
        r = qasm2.qreg(1)
        qasm2.u(q[0], 0.2, 0.0, 0.0)
        glob.u(theta=0.7, phi=0.0, lam=0.0, registers=[r])
        qasm2.parallel.u(qargs=[r[0]], theta=0.3, phi=0.0, lam=0.0)
        qasm2.u(q[0], 0.3, 0.0, 0.0)

    parallel.UOpToParallel(kernel.dialects)(kernel)
    analysis, _ = address.AddressAnalysis(kernel.dialects).run(kernel)
    operations = [
        stmt
        for stmt in kernel.callable_region.blocks[0].stmts
        if isinstance(stmt, (qasm2.dialects.glob.UGate, qasm2.dialects.parallel.UGate))
    ]
    global_gate, merged_gate = operations
    assert isinstance(global_gate, qasm2.dialects.glob.UGate)
    assert isinstance(merged_gate, qasm2.dialects.parallel.UGate)
    targets = analysis.entries[merged_gate.qargs]
    assert isinstance(targets, address.AddressReg)
    assert len(set(targets.data)) == 2


def test_merge_does_not_move_register_use_before_its_definition():
    @qasm2.extended
    def kernel():
        q = qasm2.qreg(1)
        r = qasm2.qreg(1)
        qasm2.u(q[0], 0.2, 0.0, 0.0)
        glob.u(theta=0.7, phi=0.0, lam=0.0, registers=[r])
        qasm2.u(q[0], 0.3, 0.0, 0.0)
        registers = [r]
        alias = registers[0]
        qasm2.u(alias[0], 0.3, 0.0, 0.0)

    parallel.UOpToParallel(kernel.dialects)(kernel)
    address.AddressAnalysis(kernel.dialects).run(kernel)
