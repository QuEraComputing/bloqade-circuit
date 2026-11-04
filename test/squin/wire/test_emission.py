"""Test that emission preserves source behavior and produces complete wire methods."""

import pytest
from kirin import ir
from test_roundtrip import CASES, calls, simulate, cancelling

from bloqade.qubit import stmts as qubit_stmts
from bloqade.squin.wire import stmts as wire_stmts
from bloqade.squin.passes.wire_target import ConversionTarget
from bloqade.squin.rewrite.wire.driver import reachable
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin
from bloqade.squin.analysis.validation.wire import WireValidation


def emitted(kernel: ir.Method) -> ir.Method:
    """Return the complete wire method that emission builds from `kernel`."""
    return SquinToWire().emit(kernel)


@pytest.mark.parametrize("kernel, args, expected", CASES)
def test_a_emitted_kernel_passes_the_validation_suite(kernel, args, expected):
    WireValidation().check(emitted(kernel))


@pytest.mark.parametrize("kernel, args, expected", CASES)
def test_a_emitted_kernel_gives_the_same_result_after_the_way_back(
    kernel, args, expected
):
    assert simulate(WireToSquin().emit(emitted(kernel)), *args) == expected


@pytest.mark.parametrize("kernel, args, expected", [*CASES, (calls, (), None)])
def test_a_kernel_converts_completely(kernel, args, expected):
    mt = emitted(kernel)
    assert all(not ConversionTarget.check(method) for method in reachable(mt))
    assert not any(isinstance(n, qubit_stmts.New) for n in mt.callable_region.walk())


def test_a_borrowing_call_gives_the_same_result_after_emission():
    assert simulate(WireToSquin().emit(emitted(calls))) == [[1, 0, 1, 1, 1], 4]


def test_a_register_with_constant_indices_stays_whole():
    wired = emitted(cancelling)
    statements = tuple(wired.callable_region.walk())
    assert sum(isinstance(node, wire_stmts.AllocRegister) for node in statements) == 1
    assert not any(isinstance(node, wire_stmts.Alloc) for node in statements)
    assert any(isinstance(node, wire_stmts.Borrow) for node in statements)
    assert sum(isinstance(node, wire_stmts.FreeRegister) for node in statements) == 1
