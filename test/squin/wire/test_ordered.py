"""Check ordered conversion, independent validation and source failure isolation."""

import sys
from typing import Literal

import pytest
from kirin.dialects import ilist
from test_roundtrip import CASES, calls, simulate
from test_rejections import two_registers

from bloqade import squin
from bloqade.jeff import WireToJeff
from bloqade.types import Qubit
from bloqade.squin.wire import WireConversionError
from bloqade.squin.passes.wire_target import ConversionTarget
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin
from bloqade.squin.analysis.validation.wire import WireValidation


@pytest.fixture
def forbid_reference_analysis(monkeypatch):
    class Guard:
        def find_spec(self, fullname, path=None, target=None):
            if fullname in {
                "bloqade.analysis.reference",
                "bloqade.squin.analysis.reference",
                "bloqade.jeff.analysis.wire",
            }:
                raise AssertionError(
                    "Wire conversion must use explicit values and local definitions."
                )
            return None

    monkeypatch.setattr(sys, "meta_path", [Guard(), *sys.meta_path])


@pytest.mark.parametrize("kernel, args, expected", CASES)
def test_conversion_and_validation_need_no_reference_analysis(
    forbid_reference_analysis, kernel, args, expected
):
    wired = SquinToWire().emit(kernel)
    assert not ConversionTarget.check(wired)
    WireValidation().check(wired)
    assert simulate(WireToSquin().emit(wired), *args) == expected


def test_calls_and_direct_jeff_emission_need_no_reference_analysis(
    forbid_reference_analysis,
):
    converter = SquinToWire()
    wired = converter.emit(calls)
    assert len(converter.converted) > 1
    assert simulate(WireToSquin().emit(wired)) == [[1, 0, 1, 1, 1], 4]
    emitted = WireToJeff().emit(wired)
    emitted.verify()
    emitted.verify_type()


def test_unresolved_references_fail_without_reference_analysis(
    forbid_reference_analysis,
):
    before = two_registers.code.print_str()
    with pytest.raises(WireConversionError, match="has no place"):
        SquinToWire().emit(two_registers)
    assert two_registers.code.print_str() == before


@squin.kernel
def replaced_in_loop(n: int):
    q = squin.qubit.new()
    for _ in range(n):
        q = squin.qubit.new()
        squin.x(q)
    return squin.measure(q)


@squin.kernel
def mixed_gate(flag: bool):
    a = squin.qubit.new()
    b = squin.qubit.new()
    c = squin.qubit.new()
    q = a
    if flag:
        q = b
    squin.x(q)
    squin.cx(a, c)
    return squin.broadcast.measure([a, b, c])


@pytest.mark.parametrize(
    "kernel, args, expected",
    [
        (replaced_in_loop, (0,), 0),
        (replaced_in_loop, (1,), 1),
        (replaced_in_loop, (3,), 1),
        (mixed_gate, (False,), [1, 0, 1]),
        (mixed_gate, (True,), [0, 1, 0]),
    ],
)
def test_unresolved_allocations_fail_without_changing_the_source(
    forbid_reference_analysis, kernel, args, expected
):
    before = kernel.code.print_str()
    with pytest.raises(WireConversionError):
        SquinToWire().emit(kernel)
    assert kernel.code.print_str() == before
    assert simulate(kernel, *args) == expected


@squin.kernel
def sliced_rows(rows: ilist.IList[ilist.IList[Qubit, Literal[2]], Literal[3]]):
    squin.x(rows[::-1][0][1])
    squin.x(rows[::2][1][0])


def test_slicing_nested_register_parameters_preserves_row_boundaries():
    back = WireToSquin().emit(SquinToWire().emit(sliced_rows))

    @squin.kernel
    def run_flat():
        qs = squin.qalloc(6)
        back(qs)
        return squin.broadcast.measure(qs)

    assert simulate(run_flat) == [0, 0, 0, 0, 1, 1]
