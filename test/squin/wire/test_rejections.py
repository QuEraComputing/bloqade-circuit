"""Check that unsupported references cause conversion to fail without changing the source."""

from typing import Any, Literal

import pytest
from kirin.dialects import ilist
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.types import Qubit, MeasurementResult
from bloqade.squin.wire import WireConversionError
from bloqade.squin.passes.wire_target import ConversionTarget
from bloqade.squin.passes.squin_to_wire import SquinToWire


@squin.kernel
def opaque_partner(qs: ilist.IList[Qubit, Any], j: int):
    squin.cx(qs[0], qs[j])


@squin.kernel
def calls_with_one_qubit_twice() -> ilist.IList[MeasurementResult, Any]:
    qs = squin.qalloc(3)
    squin.x(qs[0])
    squin.cx(qs[1], qs[1])
    opaque_partner(qs, 2)
    return squin.broadcast.measure(qs)


@squin.kernel
def two_registers(flag: bool) -> ilist.IList[MeasurementResult, Any]:
    a = squin.qalloc(1)
    b = squin.qalloc(1)
    q = a[0]
    if flag:
        q = b[0]
    squin.x(q)
    return squin.broadcast.measure([a[0], b[0]])


@pytest.mark.parametrize(
    "kernel, error, reason",
    [
        (calls_with_one_qubit_twice, ValidationErrorGroup, "already borrowed"),
        (two_registers, WireConversionError, "has no place"),
    ],
)
def test_unresolved_references_fail_conversion_and_preserve_the_source(
    kernel, error, reason
):
    before = kernel.code.print_str()
    helper_before = opaque_partner.code.print_str()
    with pytest.raises(error, match=reason):
        SquinToWire().emit(kernel)
    assert kernel.code.print_str() == before
    assert opaque_partner.code.print_str() == helper_before


@squin.kernel
def past_the_end():
    qs = squin.qalloc(3)
    squin.x(qs[3])


@squin.kernel
def rows_of_unknown_count(grid: ilist.IList[ilist.IList[Qubit, Literal[2]], Any]):
    squin.broadcast.x(grid[0:1][0])


@squin.kernel
def rows_of_unknown_width(grid: ilist.IList[ilist.IList[Qubit, Any], Literal[2]]):
    squin.x(grid[0][0])


@squin.kernel
def sliced_by_a_parameter(qs: ilist.IList[Qubit, Any], s: slice):
    squin.x(qs[s][0])


@squin.kernel
def mixed_broadcast(qs: ilist.IList[Qubit, Any]):
    q = squin.qubit.new()
    squin.broadcast.cx(qs, [q])


@pytest.mark.parametrize(
    "kernel, reason",
    [
        (past_the_end, "no place in this allocation"),
        (rows_of_unknown_count, "nested register slice requires constant bounds"),
        (rows_of_unknown_width, "requires known inner dimensions"),
        (sliced_by_a_parameter, "slice bounds have no supported source form"),
        (mixed_broadcast, "cannot index a heterogeneous quantum container"),
    ],
    ids=lambda x: x if isinstance(x, str) else x.sym_name,
)
def test_an_unresolved_register_form_names_its_reason(kernel, reason):
    with pytest.raises(WireConversionError, match=reason):
        SquinToWire().emit(kernel)


def test_the_conversion_target_lists_the_reference_operations_of_a_source():
    assert {"getitem", "invoke"} <= set(ConversionTarget.check(past_the_end))
