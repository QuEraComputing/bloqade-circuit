"""Test the pass that turns constant-size registers into separate wires."""

from typing import Any

import pytest
from kirin import ir
from test_forms import single_tuple, slice_in_loop, slice_in_branch, overlapping_slices
from kirin.dialects import func, ilist
from test_roundtrip import CASES, simulate

from bloqade import squin
from bloqade.types import Qubit, MeasurementResult
from bloqade.squin.wire import GateKind, stmts
from bloqade.squin.passes.wire_unpack import UnpackRegisters
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin
from bloqade.squin.analysis.validation.wire import WireValidation

REGISTERS = (
    stmts.AllocRegister,
    stmts.PackRegister,
    stmts.Borrow,
    stmts.Release,
    stmts.FreeRegister,
)


def unpacked(kernel: ir.Method) -> ir.Method:
    """Convert `kernel` to wire squin, unpack it, and check the result."""
    wired = SquinToWire().emit(kernel)
    UnpackRegisters(wired.dialects)(wired)
    WireValidation().check(wired)
    return wired


def statements(method: ir.Method) -> list[ir.Statement]:
    """Return every statement of `method`, including those in nested regions."""
    return list(method.callable_region.walk())


@squin.kernel
def repeated_h() -> ilist.IList[MeasurementResult, Any]:
    qs = squin.qalloc(2)
    squin.h(qs[0])
    squin.h(qs[0])
    squin.broadcast.x(qs)
    squin.cx(qs[0], qs[1])
    return squin.broadcast.measure(qs)


@squin.kernel
def flip(qs: ilist.IList[Qubit, Any]):
    squin.broadcast.x(qs)


@squin.kernel
def passed_to_a_call() -> ilist.IList[MeasurementResult, Any]:
    qs = squin.qalloc(2)
    flip(qs)
    return squin.broadcast.measure(qs)


@squin.kernel
def sliced() -> ilist.IList[MeasurementResult, Any]:
    qs = squin.qalloc(4)
    squin.broadcast.x(qs[1:3])
    squin.x(qs[1:3][0])
    return squin.broadcast.measure(qs)


@squin.kernel
def twice(qs: ilist.IList[Qubit, Any]):
    squin.h(qs[0])
    squin.x(qs[1])
    squin.h(qs[0])
    squin.x(qs[1])


@squin.kernel
def calls_twice() -> ilist.IList[MeasurementResult, Any]:
    qs = squin.qalloc(2)
    squin.x(qs[0])
    twice(qs)
    return squin.broadcast.measure(qs)


@pytest.mark.parametrize(
    "kernel, args, expected",
    [
        *CASES,
        (single_tuple, (7,), [7]),
        (overlapping_slices, (), [1, 1, 1]),
        (slice_in_branch, (True,), [0, 1, 1, 0]),
        (slice_in_loop, (3,), [0, 1, 1, 0]),
        (repeated_h, (), [1, 0]),
        (passed_to_a_call, (), [1, 1]),
        (sliced, (), [0, 0, 1, 0]),
        (calls_twice, (), [1, 0]),
    ],
)
def test_unpacking_keeps_the_result_of_the_kernel(kernel, args, expected):
    back = WireToSquin().emit(unpacked(kernel))
    assert simulate(back, *args) == expected


def test_a_static_kernel_keeps_no_register_and_chains_its_gates():
    nodes = statements(unpacked(repeated_h))
    assert not any(
        isinstance(node, (*REGISTERS, stmts.RegisterOperation)) for node in nodes
    )
    first, second = (
        node
        for node in nodes
        if isinstance(node, stmts.Gate) and node.kind is GateKind.H
    )
    assert second.wires[0] is first.outputs[0]


def test_a_register_that_a_loop_indexes_stays_but_loses_its_broadcasts():
    ladder = CASES[0][0]
    nodes = statements(unpacked(ladder))
    assert any(isinstance(node, stmts.AllocRegister) for node in nodes)
    assert not any(isinstance(node, stmts.RegisterOperation) for node in nodes)


def test_a_register_that_a_call_takes_stays():
    nodes = statements(unpacked(passed_to_a_call))
    assert any(isinstance(node, stmts.AllocRegister) for node in nodes)


def test_a_slice_with_constant_bounds_unpacks():
    nodes = statements(unpacked(sliced))
    assert not any(isinstance(node, (*REGISTERS, stmts.TakeSlice)) for node in nodes)


def test_borrows_of_one_element_join_across_other_elements():
    wired = SquinToWire().emit(calls_twice)
    (callee,) = {
        node.callee for node in statements(wired) if isinstance(node, func.Invoke)
    }
    UnpackRegisters(callee.dialects)(callee)
    WireValidation().check(callee)
    nodes = statements(callee)
    assert sum(isinstance(node, stmts.Borrow) for node in nodes) == 2
    first, second = (
        node
        for node in nodes
        if isinstance(node, stmts.Gate) and node.kind is GateKind.H
    )
    assert second.wires[0] is first.outputs[0]
    assert simulate(WireToSquin().emit(wired)) == [1, 0]
