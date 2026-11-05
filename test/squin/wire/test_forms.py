"""Check source forms that the emitter resolves during compilation.

Some kernels use `fold=False`, because constant folding would otherwise remove the
tuple slice, the tuple length or the unused call before the emitter sees them.
"""

from typing import Any, Literal

import pytest
from kirin.dialects import func, ilist
from test_roundtrip import trip, simulate

from bloqade import squin
from bloqade.types import Qubit
from bloqade.squin.wire import WireConversionError, stmts
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin


@squin.kernel
def empty_broadcast():
    qs = squin.qalloc(2)
    squin.broadcast.x([])
    squin.x(qs[1])
    return squin.broadcast.measure(qs)


@squin.kernel
def negative_index():
    qs = squin.qalloc(3)
    squin.x(qs[-1])
    return squin.broadcast.measure(qs)


@squin.kernel(fold=False)
def tuple_slice():
    a = squin.qubit.new()
    b = squin.qubit.new()
    c = squin.qubit.new()
    group = (a, b, c)[0:2]
    squin.x(group[1])
    return squin.broadcast.measure([a, b, c])


@squin.kernel(fold=False)
def lengths():
    qs = squin.qalloc(4)
    pair = (qs[0], qs[1])
    return len(pair) + len(qs[1:])


@squin.kernel
def classical_helper(n: int):
    return None


@squin.kernel(fold=False)
def calls_classical_helper():
    q = squin.qubit.new()
    classical_helper(1)
    squin.x(q)
    return squin.measure(q)


@pytest.mark.parametrize(
    "kernel, expected",
    [
        (negative_index, [0, 0, 1]),
        (empty_broadcast, [0, 1]),
        (tuple_slice, [0, 1, 0]),
        (lengths, 5),
        (calls_classical_helper, 1),
    ],
)
def test_a_static_form_keeps_its_result_after_the_trip(kernel, expected):
    assert simulate(kernel) == simulate(trip(kernel)) == expected


@squin.kernel
def leaf(q: Qubit):
    squin.x(q)


@squin.kernel
def left(q: Qubit):
    leaf(q)


@squin.kernel
def right(q: Qubit):
    leaf(q)


@squin.kernel
def diamond():
    q = squin.qubit.new()
    left(q)
    right(q)
    return squin.measure(q)


def test_two_callers_share_the_wire_method_of_one_callee():
    converter = SquinToWire()
    converter.emit(diamond)
    callees = {
        node.callee
        for caller in (left, right)
        for node in converter.converted[caller].code.walk()
        if isinstance(node, func.Invoke)
    }
    assert callees == {converter.converted[leaf]}
    assert simulate(trip(diamond)) == 0


@squin.kernel
def nested_row(
    grid: ilist.IList[
        ilist.IList[ilist.IList[Qubit, Literal[2]], Literal[2]], Literal[2]
    ],
):
    squin.x(grid[1][0][1])


def test_a_row_of_a_nested_row_selects_its_flat_qubit():
    back = WireToSquin().emit(SquinToWire().emit(nested_row))

    @squin.kernel
    def run_flat():
        qs = squin.qalloc(8)
        back(qs)
        return squin.broadcast.measure(qs)

    assert simulate(run_flat) == [0, 0, 0, 0, 0, 1, 0, 0]


@squin.kernel
def runtime_index(k: int):
    qs = squin.qalloc(3)
    squin.x(qs[k])
    return squin.broadcast.measure(qs)


def test_a_runtime_index_reaches_the_wire_borrow_unchanged():
    wired = SquinToWire().emit(runtime_index)
    borrow = next(node for node in wired.code.walk() if isinstance(node, stmts.Borrow))
    parameter = wired.callable_region.blocks[0].args[1]
    assert borrow.index is parameter
    assert simulate(trip(runtime_index), 2) == [0, 0, 1]


@squin.kernel
def row_count(grid: ilist.IList[ilist.IList[Qubit, Literal[2]], Any]) -> int:
    return len(grid)


def test_the_length_of_a_nested_register_counts_its_rows():
    back = WireToSquin().emit(SquinToWire().emit(row_count))

    @squin.kernel
    def run_flat() -> int:
        qs = squin.qalloc(6)
        return back(qs)

    assert simulate(run_flat) == 3


@squin.kernel
def past_a_growing_slice():
    qs = squin.qalloc(3)
    for i in range(1, 3):
        squin.x(qs[0:i][2])
    return squin.broadcast.measure(qs)


@squin.kernel
def past_the_register():
    qs = squin.qalloc(3)
    for i in range(5):
        squin.x(qs[i])
    return squin.broadcast.measure(qs)


@pytest.mark.parametrize("kernel", [past_a_growing_slice, past_the_register])
def test_an_index_that_can_lie_outside_the_register_is_rejected(kernel):
    with pytest.raises(WireConversionError, match="can lie outside"):
        SquinToWire().emit(kernel)


@squin.kernel
def single_tuple(n: int) -> tuple[int]:
    return (n,)


@squin.kernel
def measured_single_tuple():
    q = squin.qubit.new()
    squin.x(q)
    return (squin.measure(q),)


@squin.kernel
def overlapping_slices():
    qs = squin.qalloc(3)
    squin.x(qs[0])
    squin.broadcast.cx(qs[0:2], qs[1:3])
    return squin.broadcast.measure(qs)


@squin.kernel
def slice_in_branch(flag: bool):
    qs = squin.qalloc(4)
    if flag:
        squin.broadcast.x(qs[1:3])
    return squin.broadcast.measure(qs)


@squin.kernel
def slice_in_loop(n: int):
    qs = squin.qalloc(4)
    for _ in range(n):
        squin.broadcast.x(qs[1:3])
    return squin.broadcast.measure(qs)


@pytest.mark.parametrize(
    "kernel, args, expected",
    [
        (single_tuple, (7,), [7]),
        (measured_single_tuple, (), [1]),
        (overlapping_slices, (), [1, 1, 1]),
        (slice_in_branch, (True,), [0, 1, 1, 0]),
        (slice_in_branch, (False,), [0, 0, 0, 0]),
        (slice_in_loop, (3,), [0, 1, 1, 0]),
    ],
)
def test_a_form_keeps_its_result_and_its_shape_after_the_trip(kernel, args, expected):
    assert simulate(kernel, *args) == simulate(trip(kernel), *args) == expected


@squin.kernel
def slice_of_parameter(qs: ilist.IList[Qubit, Literal[4]]):
    squin.broadcast.x(qs[1:3])


def test_a_slice_of_a_register_parameter_keeps_its_qubits():
    back = trip(slice_of_parameter)

    @squin.kernel
    def run_flat():
        qs = squin.qalloc(4)
        back(qs)
        return squin.broadcast.measure(qs)

    assert simulate(run_flat) == [0, 1, 1, 0]
