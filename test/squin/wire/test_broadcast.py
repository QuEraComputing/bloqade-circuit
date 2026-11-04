"""Test broadcasts whose register lengths depend on runtime inputs."""

import math
from typing import Any

import cirq
import numpy as np
import pytest
from kirin.dialects import func, ilist
from test_roundtrip import simulate

from bloqade import squin, native
from bloqade.types import Qubit
from bloqade.pyqrack import DynamicMemorySimulator
from bloqade.squin.wire import Operation, RegisterOperation
from bloqade.squin.wire.sources import source_of
from bloqade.native.dialects.gate import stmts as native_stmts
from bloqade.squin.passes.wire_target import ConversionTarget
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin
from bloqade.squin.analysis.validation.wire import WireValidation


@squin.kernel
def flip_all(qs: ilist.IList[Qubit, Any]):
    squin.broadcast.x(qs)


@squin.kernel
def unknown_length(n: int):
    qs = squin.qalloc(n)
    flip_all(qs)
    return squin.broadcast.measure(qs)


@squin.kernel
def paired(n: int):
    a = squin.qalloc(n)
    b = squin.qalloc(n)
    squin.broadcast.x(a)
    squin.broadcast.cx(a, b)
    return squin.broadcast.measure(b)


@squin.kernel
def three_registers(n: int):
    a = squin.qalloc(n)
    b = squin.qalloc(n)
    c = squin.qalloc(n)
    squin.broadcast.x(a)
    squin.broadcast.x(b)
    squin.broadcast.h(c)
    squin.broadcast.ccz(a, b, c)
    squin.broadcast.h(c)
    return squin.broadcast.measure(c)


@squin.kernel
def adjoints_and_reset(n: int):
    qs = squin.qalloc(n)
    squin.broadcast.sqrt_x(qs)
    squin.broadcast.sqrt_x_adj(qs)
    squin.broadcast.rx(math.pi, qs)
    squin.broadcast.reset(qs)
    return squin.broadcast.measure(qs)


@squin.kernel
def mismatched(n: int, m: int):
    a = squin.qalloc(n)
    b = squin.qalloc(m)
    squin.broadcast.cx(a, b)


@native.kernel
def native_broadcast(n: int):
    qs = squin.qalloc(n)
    native.broadcast.rx(math.pi, qs)
    native.broadcast.rz(0.7, qs)
    native.cz(qs[0], qs[1])
    return squin.broadcast.measure(qs)


@native.kernel
def native_phases(n: int, m: int):
    a = squin.qalloc(n)
    b = squin.qalloc(m)
    native.broadcast.rx(0.7, a)
    native.broadcast.ry(0.3, b)
    native.broadcast.cz(a, b)
    native.broadcast.rz(0.9, b)


@squin.kernel
def paired_noise(n: int, m: int):
    a = squin.qalloc(n)
    b = squin.qalloc(m)
    squin.broadcast.depolarize2(0.0, a, b)
    probabilities = [
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    ]
    squin.broadcast.two_qubit_pauli_channel(probabilities, a, b)
    return squin.broadcast.measure(b)


@pytest.mark.parametrize(
    "kernel, bit",
    [(unknown_length, 1), (paired, 1), (three_registers, 1), (adjoints_and_reset, 0)],
)
@pytest.mark.parametrize("n", [0, 1, 4])
def test_runtime_broadcasts_emit_completely_and_preserve_results(kernel, bit, n):
    converter = SquinToWire()
    wired = converter.emit(kernel)
    assert ConversionTarget.check(wired) == []
    assert any(
        isinstance(node, RegisterOperation) for node in wired.callable_region.walk()
    )
    WireValidation().check(wired)
    back = WireToSquin().emit(wired)
    back.verify_type()
    assert simulate(back, n) == simulate(kernel, n) == [bit] * n


def test_an_unknown_length_broadcast_keeps_a_borrowing_call():
    wired = SquinToWire().emit(unknown_length)
    call = next(
        node for node in wired.callable_region.walk() if isinstance(node, func.Invoke)
    )
    assert call.callee.sym_name == "flip_all"
    assert ConversionTarget.check(call.callee) == []


@pytest.mark.parametrize("sizes", [(0, 2), (3, 1), (1, 3)])
def test_paired_broadcasts_of_unequal_lengths_fail_like_the_source(sizes):
    back = WireToSquin().emit(SquinToWire().emit(mismatched))
    with pytest.raises(RuntimeError, match="controls but"):
        simulate(mismatched, *sizes)
    with pytest.raises(RuntimeError, match="controls but"):
        simulate(back, *sizes)


@pytest.mark.parametrize("n", [2, 4])
def test_native_broadcasts_preserve_their_gates_and_results(n):
    wired = SquinToWire().emit(native_broadcast)
    sources = {
        source_of(node).source
        for node in wired.callable_region.walk()
        if isinstance(node, Operation)
    }
    assert {native_stmts.CZ, native_stmts.R, native_stmts.Rz} <= sources
    back = WireToSquin().emit(wired)
    back.verify_type()
    assert simulate(back, n) == simulate(native_broadcast, n) == [1] * n


@pytest.mark.parametrize("sizes", [(0, 2), (2, 2), (3, 1), (1, 3)])
def test_native_angles_and_shortest_list_broadcasts_preserve_the_state_vector(sizes):
    back = WireToSquin().emit(SquinToWire().emit(native_phases))
    back.verify_type()
    simulator = DynamicMemorySimulator()
    expected = np.asarray(simulator.state_vector(native_phases, args=sizes))
    actual = np.asarray(simulator.state_vector(back, args=sizes))
    cirq.testing.assert_allclose_up_to_global_phase(actual, expected, atol=1e-6)


@pytest.mark.parametrize("sizes", [(0, 2), (2, 2), (3, 1), (1, 3)])
def test_noise_broadcasts_stop_at_the_shortest_list(sizes):
    back = WireToSquin().emit(SquinToWire().emit(paired_noise))
    back.verify_type()
    n, m = sizes
    expected = [1] * min(n, m) + [0] * max(m - n, 0)
    assert simulate(back, *sizes) == simulate(paired_noise, *sizes) == expected


@native.kernel
def separate_qubits():
    qs = squin.qalloc(3)
    native.broadcast.rx(math.pi, [qs[0], qs[2]])
    return squin.broadcast.measure(qs)


@squin.kernel
def overlapping_lists():
    qs = squin.qalloc(3)
    squin.x(qs[0])
    squin.broadcast.cx([qs[0], qs[1]], [qs[1], qs[2]])
    return squin.broadcast.measure(qs)


def test_a_broadcast_over_separate_qubits_stays_one_statement():
    wired = SquinToWire().emit(separate_qubits)
    (gate,) = (
        node
        for node in wired.callable_region.walk()
        if isinstance(node, Operation)
        and not isinstance(node, RegisterOperation)
        and node.name == "gate"
    )
    assert len(gate.groups) == 2
    back = WireToSquin().emit(wired)
    rotations = [
        node for node in back.callable_region.walk() if isinstance(node, native_stmts.R)
    ]
    assert len(rotations) == 1
    assert simulate(back) == simulate(separate_qubits) == [1, 0, 1]


def test_groups_that_share_a_qubit_stay_in_source_order():
    wired = SquinToWire().emit(overlapping_lists)
    gates = [
        node
        for node in wired.callable_region.walk()
        if isinstance(node, Operation) and node.name == "gate" and node.label == "cx"
    ]
    assert [len(gate.groups) for gate in gates] == [1, 1]
    assert (
        simulate(WireToSquin().emit(wired)) == simulate(overlapping_lists) == [1, 1, 1]
    )
