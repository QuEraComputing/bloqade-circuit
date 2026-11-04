"""Test the merge of native single-qubit rotation runs."""

import math
import itertools
import importlib.util

import cirq
import numpy as np
import pytest
from kirin import ir

from bloqade import squin, native
from bloqade.pyqrack import DynamicMemorySimulator
from bloqade.squin.wire import Gate, GateKind
from bloqade.native.dialects.gate import stmts as native_stmts
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin
from bloqade.squin.passes.wire_rotations import (
    MergeNativeRotations,
    merge_native_rotations,
)
from bloqade.squin.rewrite.wire.rotations import decompose
from bloqade.squin.analysis.validation.wire import WireValidation

X = np.array([[0, 1], [1, 0]], dtype=complex)
Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
Z = np.diag([1, -1]).astype(complex)


def r(phi: float, theta: float) -> np.ndarray:
    """Return the matrix of the native `R(phi, theta)` with angles in turns."""
    axis = math.cos(math.tau * phi) * X + math.sin(math.tau * phi) * Y
    return math.cos(math.pi * theta) * np.eye(2) - 1j * math.sin(math.pi * theta) * axis


def rz(turns: float) -> np.ndarray:
    """Return the matrix of the native `Rz(turns)`."""
    return math.cos(math.pi * turns) * np.eye(2) - 1j * math.sin(math.pi * turns) * Z


def product(spec) -> np.ndarray:
    """Return the matrix of a merged run in time order."""
    matrix = np.eye(2, dtype=complex)
    for kind, angles in spec:
        gate = r(*angles) if kind is GateKind.NATIVE_R else rz(*angles)
        matrix = gate @ matrix
    return matrix


def rotations(kernel: ir.Method) -> int:
    """Return the number of native `R` statements in `kernel`."""
    return sum(isinstance(n, native_stmts.R) for n in kernel.callable_region.walk())


def same_state(kernel: ir.Method, merged: ir.Method, *args) -> None:
    """Check that both kernels prepare one state, up to a global phase."""
    simulator = DynamicMemorySimulator()
    expected = np.asarray(simulator.state_vector(kernel, args=args))
    actual = np.asarray(simulator.state_vector(merged, args=args))
    cirq.testing.assert_allclose_up_to_global_phase(actual, expected, atol=1e-6)


CLIFFORDS = [
    product(((GateKind.NATIVE_R, (phi, theta)), (GateKind.NATIVE_RZ, (lam,))))
    for phi, theta, lam in itertools.product(
        (0, 0.25, 0.5, 0.75), (0, 0.25, 0.5), (0, 0.25, 0.5, 0.75)
    )
]


@pytest.mark.parametrize("seed", range(20))
def test_the_decomposition_rebuilds_a_random_unitary(seed):
    unitary = cirq.testing.random_unitary(2, random_state=seed)
    cirq.testing.assert_allclose_up_to_global_phase(
        product(decompose(unitary)), unitary, atol=1e-9
    )


@pytest.mark.parametrize("unitary", CLIFFORDS)
def test_the_decomposition_rebuilds_a_clifford_with_grid_angles(unitary):
    spec = decompose(unitary)
    cirq.testing.assert_allclose_up_to_global_phase(product(spec), unitary, atol=1e-9)
    for _, angles in spec:
        assert all(angle * 8 == round(angle * 8) for angle in angles)


def test_the_identity_and_a_diagonal_matrix_give_short_forms():
    assert decompose(np.eye(2)) == ()
    assert decompose(rz(0.3)) == ((GateKind.NATIVE_RZ, (0.3,)),)


@native.kernel
def twice_cx():
    qs = squin.qalloc(2)
    native.cx(qs[0], qs[1])
    native.cx(qs[0], qs[1])


@native.kernel
def undone_layer():
    qs = squin.qalloc(3)
    native.h(qs[0])
    native.broadcast.rx(0.3, [qs[0], qs[2]])
    native.broadcast.rx(-0.3, [qs[2], qs[0]])


@native.kernel
def split_layer():
    qs = squin.qalloc(2)
    native.broadcast.rx(0.3, [qs[0], qs[1]])
    native.rx(0.4, qs[0])


@native.kernel
def runtime_angle(theta: float):
    q = squin.qalloc(1)
    native.rx(theta, q[0])
    native.rx(theta, q[0])


@native.kernel
def whole_register(n: int):
    qs = squin.qalloc(n)
    native.broadcast.rx(0.3, qs)
    native.broadcast.ry(0.2, qs)


def test_cx_twice_keeps_2_of_its_4_pulses():
    merged = merge_native_rotations(twice_cx)
    assert rotations(merged) == 2
    same_state(twice_cx, merged)


def test_a_layer_and_its_inverse_on_one_group_vanish():
    merged = merge_native_rotations(undone_layer)
    assert rotations(merged) == 1
    same_state(undone_layer, merged)


def test_a_merge_never_splits_a_broadcast():
    merged = merge_native_rotations(split_layer)
    assert rotations(merged) == 2
    same_state(split_layer, merged)


def test_a_runtime_angle_ends_the_run():
    merged = merge_native_rotations(runtime_angle)
    assert rotations(merged) == 2
    same_state(runtime_angle, merged, 0.7)


# PyQrack has no state vector for 0 qubits, so the lengths start at 1.
@pytest.mark.parametrize("n", [1, 3])
def test_broadcasts_over_one_register_merge_for_any_length(n):
    merged = merge_native_rotations(whole_register)
    assert rotations(merged) == 1
    same_state(whole_register, merged, n)


def test_the_merged_wire_method_passes_validation():
    wired = SquinToWire().emit(twice_cx)
    MergeNativeRotations(wired.dialects)(wired)
    WireValidation().check(wired)
    gates = [n for n in wired.callable_region.walk() if isinstance(n, Gate)]
    assert [gate.kind for gate in gates].count(GateKind.NATIVE_R) == 2


GATES = (
    "native.rx({angle}, qs[{target}])",
    "native.ry({angle}, qs[{target}])",
    "native.rz({angle}, qs[{target}])",
    "native.cz(qs[0], qs[1])",
)


def random_circuit(seed: int, folder) -> ir.Method:
    """Write a random native kernel on 2 qubits to a module in `folder` and load it.

    Kirin lowers a kernel from its source file, so each circuit needs a file.
    """
    rng = np.random.default_rng(seed)
    lines = []
    for _ in range(12):
        gate = GATES[int(rng.integers(len(GATES)))]
        angle = float(rng.choice([math.pi / 2, math.pi, rng.random()]))
        lines.append("    " + gate.format(angle=angle, target=int(rng.integers(2))))
    source = "\n".join(
        [
            "from bloqade import squin, native",
            "",
            "",
            "@native.kernel",
            "def circuit():",
            "    qs = squin.qalloc(2)",
            *lines,
            "",
        ]
    )
    path = folder / f"circuit_{seed}.py"
    path.write_text(source)
    spec = importlib.util.spec_from_file_location(f"circuit_{seed}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.circuit


@pytest.mark.parametrize("seed", range(10))
def test_a_random_native_circuit_keeps_its_state_and_loses_no_pulse(seed, tmp_path):
    circuit = random_circuit(seed, tmp_path)
    merged = merge_native_rotations(circuit)
    plain = WireToSquin().emit(SquinToWire().emit(circuit))
    assert rotations(merged) <= rotations(plain)
    same_state(circuit, merged)
