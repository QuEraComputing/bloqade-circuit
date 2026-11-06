"""Tests that a squin kernel survives the trip to jeff, to a file, and back to squin."""

import math
import tempfile
from typing import Any, Literal
from pathlib import Path

import pytest
from kirin import ir, types
from kirin.dialects import math as kmath, ilist
from kirin.dialects.ilist import IList

from bloqade import squin
from bloqade.jeff import JeffToSquin, SquinToJeff, emit_jeff, load_jeff
from bloqade.types import Qubit, QubitType, MeasurementResult
from bloqade.squin.gate import _interface as gate
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin

from .build import validate
from .helpers import rejected, simulate, as_python


def _plain(value):
    """Return `value` as plain Python: bits become ints, lists element-wise."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (IList, list, tuple)):
        items = value.data if isinstance(value, IList) else value
        return [_plain(v) for v in items]
    return int(value)


def _same(a, b) -> bool:
    """Return True if `a` and `b` agree, with floats compared by closeness."""
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        return a == b or math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    return a == b


def returned(kernel: ir.Method) -> ir.Method:
    """Return the squin kernel that comes back from jeff, through a jeff file."""
    jeff = SquinToJeff().emit(kernel)
    validate(jeff)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "kernel.jeff"
        emit_jeff(jeff).write_out(str(path))
        return JeffToSquin().emit(load_jeff(str(path)))


@squin.kernel
def flip(q: Qubit) -> Qubit:
    squin.x(q)
    return q


@squin.kernel
def fresh() -> Qubit:
    return squin.qubit.new()


@squin.kernel
def flipped_fresh() -> MeasurementResult:
    q = fresh()
    flip(q)
    return squin.measure(q)


@squin.kernel
def counted(n: int) -> MeasurementResult:
    qs = squin.qalloc(3)
    total = 0
    for k in range(n):
        squin.x(qs[k % 3])
        total = total + 1
    flip(qs[1])
    if total > 3:
        squin.x(qs[2])
    return squin.measure(qs[2])


@squin.kernel
def bell() -> tuple[MeasurementResult, MeasurementResult]:
    a = squin.qubit.new()
    b = squin.qubit.new()
    squin.h(a)
    squin.cx(a, b)
    return squin.measure(a), squin.measure(b)


@squin.kernel
def ghz() -> tuple[MeasurementResult, MeasurementResult, MeasurementResult]:
    qs = squin.qalloc(3)
    squin.h(qs[0])
    for i in range(2):
        squin.cx(qs[i], qs[i + 1])
    return squin.measure(qs[0]), squin.measure(qs[1]), squin.measure(qs[2])


@squin.kernel
def marked(n: int) -> ilist.IList[MeasurementResult, Any]:
    qs = squin.qalloc(3)
    for k in range(n):
        squin.x(qs[k])
    return squin.broadcast.measure(qs)


@squin.kernel
def inverted(n: int) -> ilist.IList[bool, Any]:
    qs = squin.qalloc(2)
    squin.x(qs[n])
    return squin.broadcast.is_zero(squin.broadcast.measure([qs[0], qs[1]]))


@squin.kernel
def decided(flag: bool) -> int:
    q = squin.qubit.new()
    if flag:
        squin.x(q)
    total = 0
    if squin.measure(q):
        total = total + 5
    return total


@squin.kernel
def statements(n: int) -> MeasurementResult:
    q = squin.qubit.new()
    r = squin.qubit.new()
    gate.rx(0.5, [q])
    gate.t([r], adjoint=True)
    gate.cx([q], [r])
    gate.swap([q], [r])
    for _ in range(n):
        gate.x([r])
    squin.reset(q)
    return squin.measure(r)


@squin.kernel
def classical(x: float, k: int) -> tuple[float, int, bool, float, float]:
    weights = [0.5, 1.5, 2.5]
    scaled = -x * weights[k] + kmath.fabs(x)
    angle = kmath.atan2(scaled, 2.0)
    pair = (k * 2, k < 2)
    halved = kmath.log(x + 3.0, 2.0)
    return angle, pair[0] + len(weights), pair[1], kmath.sin(x) ** 2, halved


@squin.kernel
def arithmetic(
    a: int, b: int, x: float
) -> tuple[int, int, bool, bool, float, int, int, int]:
    values = [a, b, a + b]
    table = [7, 8, 9]
    scaled = [x, 2.0 * x]
    total = len(values) + len(scaled)
    odd = a != b and not (a < 0 or b < 0)
    size = abs(-a) + abs(b)
    magnitude = abs(-x)
    copy = size
    quotient = (-7 * a) // b
    remainder = (-7 * a) % b
    return values[b] + table[a], total, odd, True, magnitude, copy, quotient, remainder


@squin.kernel
def inverted_int(a: int) -> int:
    return ~a


@squin.kernel
def divided(x: float, y: float) -> tuple[float, float, float]:
    return x / y, 3 / x, kmath.log(x, y)


@squin.kernel
def nested(n: int, flag: bool):
    qs = squin.qalloc(3)
    q = squin.qubit.new()
    for _ in range(n):
        for j in range(2):
            if flag:
                squin.x(qs[j])
            else:
                squin.x(q)
        squin.x(qs[2])
    return squin.broadcast.measure([qs[0], qs[1], qs[2], q])


@squin.kernel
def sequential(n: int):
    q = squin.qubit.new()
    p = squin.qubit.new()
    for _ in range(n):
        squin.x(q)
    for _ in range(n + 1):
        squin.x(q)
        squin.x(p)
    return squin.broadcast.measure([q, p])


@squin.kernel
def branches(flag: bool):
    a = squin.qubit.new()
    b = squin.qubit.new()
    if flag:
        squin.x(a)
    else:
        squin.x(b)
    return squin.broadcast.measure([a, b])


@squin.kernel
def born_inside(n: int) -> int:
    q = squin.qubit.new()
    total = 0
    for _ in range(n):
        t = squin.qubit.new()
        squin.x(t)
        squin.cx(t, q)
        total = total + 1
    if squin.measure(q):
        total = total + 10
    return total


@squin.kernel
def tuple_in_branch(n: int, a: float, b: float):
    q = squin.qubit.new()
    pair = (a, b)
    if n > 0:
        squin.rx(pair[1], q)
    return squin.measure(q)


@squin.kernel
def touch_list(qs: ilist.IList[Qubit, Any], q: Qubit, n: int, flag: bool) -> Qubit:
    for k in range(n):
        if flag:
            squin.x(qs[k])
        squin.cx(q, qs[0])
    return q


@squin.kernel
def list_to_a_call(n: int, flag: bool) -> ilist.IList[MeasurementResult, Any]:
    qs = squin.qalloc(3)
    r = squin.qubit.new()
    squin.x(r)
    touch_list(qs, r, n, flag)
    return squin.broadcast.measure(qs)


@squin.kernel
def kick(q: Qubit, k: int) -> int:
    for _ in range(k):
        squin.x(q)
    return k + 1


@squin.kernel
def kicks_in_a_loop(n: int, flag: bool):
    qs = squin.qalloc(3)
    a = squin.qubit.new()
    total = 0
    for k in range(n):
        if flag:
            total = total + kick(qs[k], k)
            squin.x(a)
        else:
            for j in range(2):
                squin.cx(a, qs[j])
            total = total + kick(a, 1)
        squin.x(qs[2])
    return squin.broadcast.measure([qs[0], qs[1], qs[2], a]), total


@squin.kernel
def logic(a: int, b: int, x: float):
    # Python's `and` and `or` return an operand, so `not` compares truth values.
    return [not a, not (a and b), not (a or b), not x, not (x and b)]


@squin.kernel
def integer_operands(a: int, b: int):
    return (a and b), (a or b)


@squin.kernel
def float_operands(a: float, b: float):
    return (a and b), (a or b)


@squin.kernel
def integer_or(a: int, b: int):
    return a or b


@squin.kernel
def operands_in_calls_and_loops(a: int, b: int, n: int):
    value = integer_or(a, b)
    total = 0
    for i in range(n):
        total = total + (a and b) + value
    return total


@pytest.mark.parametrize(
    "kernel, args, expected",
    [
        (integer_operands, (2, 3), (3, 2)),
        (integer_operands, (0, 3), (0, 3)),
        (integer_operands, (-2, 0), (0, -2)),
        (float_operands, (2.5, -3.5), (-3.5, 2.5)),
        (float_operands, (-0.0, 3.5), (-0.0, 3.5)),
        (float_operands, (-2.5, 0.0), (0.0, -2.5)),
        (operands_in_calls_and_loops, (2, 3, 0), 0),
        (operands_in_calls_and_loops, (2, 3, 3), 15),
        (operands_in_calls_and_loops, (0, 3, 3), 9),
    ],
)
def test_boolean_operands_survive_wire_and_jeff_conversion(kernel, args, expected):
    before = kernel.code.print_str()
    wired = SquinToWire().emit(kernel)
    for method in (kernel, WireToSquin().emit(wired), returned(kernel)):
        actual = simulate(method, *args)
        assert actual == expected
        if isinstance(expected, tuple):
            assert tuple(type(value) for value in actual) == tuple(
                type(value) for value in expected
            )
            if args[0] == -0.0 and isinstance(args[0], float):
                assert math.copysign(1.0, actual[0]) == -1.0
    assert kernel.code.print_str() == before


@squin.kernel
def flipped_register(n: int):
    qs = squin.qalloc(n)
    for i in range(n):
        squin.x(qs[i])
    return qs


@squin.kernel
def flips_three(
    qs: ilist.IList[Qubit, Literal[3]],
) -> ilist.IList[MeasurementResult, Literal[3]]:
    squin.broadcast.x(qs)
    return squin.broadcast.measure(qs)


@squin.kernel
def three_through_a_parameter() -> ilist.IList[MeasurementResult, Literal[3]]:
    # The callee reads the register length from its parameter type.
    qs = squin.qalloc(3)
    return flips_three(qs)


@squin.kernel
def sized_by_caller():
    # The callee allocates the register, and only the caller knows its size.
    return squin.broadcast.measure(flipped_register(3))


@squin.kernel
def ladder() -> ilist.IList[MeasurementResult, Any]:
    qs = squin.qalloc(4)
    squin.x(qs[0])
    for i in range(3):
        squin.cx(qs[i], qs[i + 1])
    return squin.broadcast.measure(qs)


@squin.kernel
def flip_two(qs: ilist.IList[Qubit, Literal[2]]):
    squin.x(qs[0])
    squin.x(qs[1])


@squin.kernel
def sliced_call() -> ilist.IList[MeasurementResult, Any]:
    qs = squin.qalloc(4)
    flip_two(qs[1:3])
    squin.x(qs[1:3][1])
    return squin.broadcast.measure(qs)


@squin.kernel
def sliding(n: int) -> ilist.IList[MeasurementResult, Any]:
    qs = squin.qalloc(4)
    for i in range(3):
        flip_two(qs[i : i + 2 : 1])
    return squin.broadcast.measure(qs)


DETERMINISTIC = [
    (ladder, (), [1, 1, 1, 1]),
    (sliced_call, (), [0, 1, 0, 0]),
    (sliding, (0,), [1, 0, 0, 1]),
    (arithmetic, (2, 1, 1.5), [10, 5, 1, 1, 1.5, 3, -14, 0]),
    (arithmetic, (1, 2, 0.5), [11, 5, 1, 1, 0.5, 3, -4, 1]),
    (statements, (1,), 0),
    (statements, (2,), 1),
    (classical, (1.0, 2), [math.atan2(-2.5 + 1.0, 2.0), 7, 0, math.sin(1.0) ** 2, 2.0]),
    (flipped_fresh, (), 1),
    (counted, (3,), 1),
    (counted, (4,), 0),
    (marked, (2,), [1, 1, 0]),
    (decided, (True,), 5),
    (decided, (False,), 0),
    (inverted_int, (2,), -3),
    (divided, (8.0, 2.0), [4.0, 0.375, 3.0]),
    (sized_by_caller, (), [1, 1, 1]),
    (three_through_a_parameter, (), [1, 1, 1]),
    (logic, (2, 1, 0.0), [0, 0, 0, 1, 1]),
    (logic, (0, 3, 0.5), [1, 1, 0, 0, 0]),
    (nested, (1, True), [1, 1, 1, 0]),
    (nested, (2, True), [0, 0, 0, 0]),
    (nested, (3, False), [0, 0, 1, 0]),
    (sequential, (1,), [1, 0]),
    (sequential, (2,), [1, 1]),
    (branches, (True,), [1, 0]),
    (branches, (False,), [0, 1]),
    (born_inside, (2,), 2),
    (born_inside, (3,), 13),
    (tuple_in_branch, (1, 0.0, math.pi), 1),
    (tuple_in_branch, (1, math.pi, 0.0), 0),
    (list_to_a_call, (1, False), [1, 0, 0]),
    (list_to_a_call, (2, True), [1, 1, 0]),
    (list_to_a_call, (3, True), [0, 1, 1]),
    (kicks_in_a_loop, (3, True), [[0, 1, 1, 1], 6]),
    (kicks_in_a_loop, (2, False), [[1, 1, 0, 0], 4]),
]

# pyqrack has no rule for `is_zero` on the squin source, so this one skips it.
DIRECT_REFUSALS = {
    flipped_fresh: "cannot return qubits",
    counted: "cannot return qubits",
    list_to_a_call: "cannot return qubits",
    sized_by_caller: "cannot return qubits",
}
DETERMINISTIC_AFTER_THE_TRIP = [
    case for case in DETERMINISTIC if case[0] not in DIRECT_REFUSALS
] + [(inverted, (1,), [1, 0])]


@pytest.mark.parametrize("kernel, reason", DIRECT_REFUSALS.items())
def test_direct_emission_reports_unsupported_call_contracts(kernel, reason):
    before = kernel.code.print_str()
    with rejected(reason):
        SquinToJeff().emit(kernel)
    assert kernel.code.print_str() == before


@pytest.mark.parametrize("kernel, args, expected", DETERMINISTIC)
def test_a_deterministic_kernel_simulates_the_same_before_the_trip(
    kernel, args, expected
):
    assert _same(_plain(simulate(kernel, *args)), expected)


@pytest.mark.parametrize("kernel, args, expected", DETERMINISTIC_AFTER_THE_TRIP)
def test_a_deterministic_kernel_gives_the_expected_result_after_the_trip(
    kernel, args, expected
):
    assert _same(_plain(simulate(returned(kernel), *args)), expected)


@squin.kernel
def bell_list() -> ilist.IList[MeasurementResult, Any]:
    a = squin.qubit.new()
    b = squin.qubit.new()
    squin.h(a)
    squin.cx(a, b)
    return squin.broadcast.measure([a, b])


@squin.kernel
def ghz_register() -> ilist.IList[MeasurementResult, Any]:
    qs = squin.qalloc(3)
    squin.h(qs[0])
    for i in range(2):
        squin.cx(qs[i], qs[i + 1])
    return squin.broadcast.measure(qs)


@pytest.mark.parametrize("kernel", [bell, ghz, bell_list, ghz_register])
def test_an_entangled_kernel_stays_correlated_after_the_trip(kernel):
    back = returned(kernel)
    for _ in range(8):
        bits = as_python(simulate(back))
        assert len(set(bits)) == 1


@squin.kernel
def grid(qss: ilist.IList[ilist.IList[Qubit, Literal[2]], Literal[3]]):
    squin.x(qss[0][1])
    for i in range(2):
        squin.cx(qss[i][1], qss[i + 1][0])
    squin.x(qss[2][0])
    squin.x(qss[2][1])


@squin.kernel
def grid_from_rows() -> ilist.IList[MeasurementResult, Any]:
    qs = squin.qalloc(6)
    grid([qs[0:2], qs[2:4], qs[4:6]])
    return squin.broadcast.measure(qs)


def test_a_register_of_registers_comes_back_as_one_flat_register():
    """Jeff stores the rows of `qss` one after another in one register."""
    back = returned(grid)
    (param,) = back.callable_region.blocks[0].args[1:]
    assert param.type.is_subseteq(ilist.IListType[QubitType, types.Any])

    @squin.kernel
    def flat_grid() -> ilist.IList[MeasurementResult, Any]:
        qs = squin.qalloc(6)
        back(qs)
        return squin.broadcast.measure(qs)

    expected = [0, 1, 1, 0, 1, 1]
    assert _plain(simulate(grid_from_rows)) == expected
    assert _plain(simulate(flat_grid)) == expected


Measured = ilist.IList[MeasurementResult, Any]


@squin.kernel
def middle_slice() -> Measured:
    qs = squin.qalloc(4)
    squin.broadcast.x(qs[1:3])
    return squin.broadcast.measure(qs)


@squin.kernel
def tail_slice() -> Measured:
    qs = squin.qalloc(4)
    squin.broadcast.x(qs[-2:])
    return squin.broadcast.measure(qs)


@squin.kernel
def strided_slice() -> Measured:
    qs = squin.qalloc(4)
    squin.broadcast.x(qs[::2])
    return squin.broadcast.measure(qs)


@squin.kernel
def reversed_first() -> Measured:
    qs = squin.qalloc(4)
    squin.x(qs[::-1][0])
    return squin.broadcast.measure(qs)


@squin.kernel
def slice_of_a_slice() -> Measured:
    qs = squin.qalloc(6)
    squin.broadcast.x(qs[1:5][1:3])
    return squin.broadcast.measure(qs)


@squin.kernel
def row_of_a_literal_list() -> tuple[Measured, Measured]:
    qss = [squin.qalloc(2), squin.qalloc(2)]
    squin.x(qss[1][0])
    return squin.broadcast.measure(qss[0]), squin.broadcast.measure(qss[1])


@squin.kernel
def fan_out() -> Measured:
    qs = squin.qalloc(3)
    squin.x(qs[0])
    for i in range(1, 3):
        squin.cx(qs[0], qs[i])
    return squin.broadcast.measure(qs)


@squin.kernel
def squared_index() -> Measured:
    qs = squin.qalloc(4)
    for i in range(2):
        squin.x(qs[i * i + 1])
    return squin.broadcast.measure(qs)


@squin.kernel
def wrapped_index() -> Measured:
    qs = squin.qalloc(3)
    for i in range(2):
        squin.x(qs[(i + 1) % 3])
    return squin.broadcast.measure(qs)


@squin.kernel
def flip_at(qs: ilist.IList[Qubit, Any], i: int):
    squin.x(qs[i])


@squin.kernel
def index_to_a_call() -> Measured:
    qs = squin.qalloc(3)
    flip_at(qs, 2)
    return squin.broadcast.measure(qs)


@squin.kernel
def measured_branch() -> Measured:
    qs = squin.qalloc(2)
    squin.x(qs[0])
    if squin.measure(qs[0]):
        squin.x(qs[1])
    return squin.broadcast.measure(qs)


@squin.kernel
def sliced_in_a_loop() -> Measured:
    qs = squin.qalloc(4)
    for i in range(1, 3):
        squin.x(qs[0:3][i])
    return squin.broadcast.measure(qs)


@squin.kernel
def growing_slice() -> Measured:
    qs = squin.qalloc(4)
    for i in range(1, 4):
        squin.x(qs[0:i][i - 1])
    return squin.broadcast.measure(qs)


@squin.kernel
def flip_all(ps: ilist.IList[Qubit, Any]):
    squin.broadcast.x(ps)


@squin.kernel
def slice_to_any_length() -> Measured:
    qs = squin.qalloc(4)
    flip_all(qs[1:3])
    return squin.broadcast.measure(qs)


@squin.kernel
def strided_to_a_call() -> Measured:
    qs = squin.qalloc(4)
    flip_two(qs[::2])
    return squin.broadcast.measure(qs)


@squin.kernel
def loop_over_qubits() -> Measured:
    qs = squin.qalloc(3)
    for q in qs:
        squin.x(q)
    return squin.broadcast.measure(qs)


@squin.kernel
def picked_in_a_branch(flag: bool) -> Measured:
    qs = squin.qalloc(2)
    q = qs[0]
    if flag:
        q = qs[1]
    squin.x(q)
    return squin.broadcast.measure(qs)


@squin.kernel
def carried_by_a_loop(n: int) -> Measured:
    qs = squin.qalloc(2)
    q = qs[0]
    for _ in range(n):
        squin.x(q)
        q = qs[1]
    return squin.broadcast.measure(qs)


@squin.kernel
def middle_of(qs: ilist.IList[Qubit, Literal[4]]):
    return qs[1:3]


@squin.kernel
def returns_a_part() -> Measured:
    qs = squin.qalloc(4)
    squin.broadcast.x(middle_of(qs))
    return squin.broadcast.measure(qs)


@squin.kernel
def concatenated() -> Measured:
    a = squin.qalloc(2)
    b = squin.qalloc(2)
    squin.broadcast.x(a + b)
    return squin.broadcast.measure(a)


@squin.kernel
def nested_def() -> Measured:
    qs = squin.qalloc(2)

    def flip_one(q: Qubit):
        squin.x(q)

    flip_one(qs[0])
    return squin.broadcast.measure(qs)


@squin.kernel
def mapped() -> Measured:
    qs = squin.qalloc(2)

    def measure_one(q: Qubit) -> MeasurementResult:
        return squin.measure(q)

    return ilist.map(measure_one, qs)


@squin.kernel
def for_each_qubit() -> Measured:
    qs = squin.qalloc(2)

    def flip_one(q: Qubit):
        squin.x(q)

    ilist.for_each(flip_one, qs)
    return squin.broadcast.measure(qs)


@squin.kernel
def flip_rows(rows: ilist.IList[ilist.IList[Qubit, Literal[2]], Literal[2]]):
    squin.x(rows[0][0])


@squin.kernel
def literal_list_to_a_call() -> Measured:
    a = squin.qalloc(2)
    b = squin.qalloc(2)
    flip_rows([a, b])  # pyright: ignore[reportArgumentType]
    return squin.broadcast.measure(a)


# Each case holds a kernel, its arguments and the reason why jeff refuses it.
# A case without a reason must give the same result after the trip.
CASES = [
    pytest.param(middle_slice, (), None, id="qs[1:3]"),
    pytest.param(tail_slice, (), None, id="qs[-2:]"),
    pytest.param(strided_slice, (), None, id="qs[::2]"),
    pytest.param(reversed_first, (), None, id="qs[::-1][0]"),
    pytest.param(slice_of_a_slice, (), None, id="qs[1:5][1:3]"),
    pytest.param(ladder, (), None, id="cx(qs[i], qs[i + 1])"),
    pytest.param(row_of_a_literal_list, (), None, id="qss[1][0]"),
    pytest.param(sliced_call, (), None, id="qs[1:3] to a call of 2 qubits"),
    pytest.param(fan_out, (), None, id="cx(qs[0], qs[i])"),
    pytest.param(squared_index, (), None, id="qs[i * i + 1]"),
    pytest.param(wrapped_index, (), None, id="qs[(i + 1) % 3]"),
    pytest.param(index_to_a_call, (), None, id="an index to a call"),
    pytest.param(measured_branch, (), None, id="a branch on a measured bit"),
    pytest.param(sliced_in_a_loop, (), None, id="qs[0:3][i]"),
    pytest.param(growing_slice, (), None, id="qs[0:i]"),
    pytest.param(slice_to_any_length, (), None, id="qs[1:3] to a call of any length"),
    pytest.param(
        strided_to_a_call,
        (),
        "step-1 slices of known length",
        id="qs[::2] to a call",
    ),
    pytest.param(
        loop_over_qubits,
        (),
        "cannot iterate over qubits",
        id="for q in qs",
    ),
    pytest.param(
        picked_in_a_branch,
        (True,),
        "same qubit reference at each result",
        id="a qubit picked in a branch",
    ),
    pytest.param(
        carried_by_a_loop,
        (2,),
        "yield each qubit reference that it carries",
        id="a qubit carried by a loop",
    ),
    pytest.param(
        returns_a_part,
        (),
        "cannot return qubits",
        id="a call that returns qs[1:3]",
    ),
    pytest.param(concatenated, (), None, id="a + b of registers"),
    pytest.param(
        nested_def,
        (),
        "requires function, loop or branch regions",
        id="a call of a nested def",
    ),
    pytest.param(
        mapped,
        (),
        "'map' has no wire form for qubit references",
        id="ilist.map over qubits",
    ),
    pytest.param(
        for_each_qubit,
        (),
        "'for_each' has no wire form for qubit references",
        id="ilist.for_each over qubits",
    ),
    pytest.param(
        literal_list_to_a_call,
        (),
        "step-1 slices of known length",
        id="a literal list of registers to a call",
    ),
]


@pytest.mark.parametrize("kernel, args, refusal", CASES)
def test_a_kernel_survives_the_trip_or_jeff_names_the_refusal(kernel, args, refusal):
    if refusal is not None:
        with rejected(refusal):
            SquinToJeff().emit(kernel)
        return
    before = _plain(simulate(kernel, *args))
    assert _same(_plain(simulate(returned(kernel), *args)), before)


@squin.kernel
def counted_from_false(n: int) -> int:
    total = False
    for _ in range(n):
        total = total + 1
    return total


@squin.kernel
def measured_or_five(flag: bool) -> int:
    q = squin.qubit.new()
    squin.x(q)
    value = squin.measure(q)
    if flag:
        value = 5
    return value


@pytest.mark.parametrize(
    "kernel, args",
    [
        (counted_from_false, (0,)),
        (counted_from_false, (3,)),
        (measured_or_five, (True,)),
        (measured_or_five, (False,)),
    ],
)
def test_state_that_widens_from_a_bit_to_an_int_survives_the_trip(kernel, args):
    assert _same(
        _plain(simulate(returned(kernel), *args)), _plain(simulate(kernel, *args))
    )


@squin.kernel
def flip_times(q: Qubit, n: int):
    for _ in range(n):
        squin.x(q)


@squin.kernel
def calls_a_subroutine() -> ilist.IList[MeasurementResult, Any]:
    qs = squin.qalloc(2)
    flip_times(qs[1], 3)
    return squin.broadcast.measure(qs)


def test_squin_from_jeff_with_a_subroutine_goes_to_jeff_again():
    once = returned(calls_a_subroutine)
    twice = JeffToSquin().emit(SquinToJeff().emit(once))
    expected = _plain(simulate(calls_a_subroutine))
    assert _same(_plain(simulate(once)), expected)
    assert _same(_plain(simulate(twice)), expected)


@squin.kernel
def flip_register_with_count(qs: ilist.IList[Qubit, Any], count: int) -> tuple[int]:
    squin.x(qs[0])
    return (count,)


@squin.kernel
def nested_register_call(qs: ilist.IList[Qubit, Any], count: int) -> tuple[int]:
    return flip_register_with_count(qs, count)


@squin.kernel
def measure_after_register_call(flag: bool, count: int):
    qs = squin.qalloc(3)
    result = nested_register_call(qs, count)
    for _ in range(count):
        squin.x(qs[1])
    if flag:
        squin.x(qs[2])
    return squin.broadcast.measure(qs), result[0]


@pytest.mark.parametrize("flag", [False, True])
@pytest.mark.parametrize("count", [0, 1, 2])
def test_register_lengths_survive_calls_gates_loops_and_branches(flag, count):
    restored = returned(measure_after_register_call)
    expected = [[1, count % 2, int(flag)], count]
    assert _plain(simulate(restored, flag, count)) == expected
    assert _plain(simulate(measure_after_register_call, flag, count)) == expected


@squin.kernel
def negative_allocation_length():
    qs = squin.qalloc(-2)
    return len(qs)


@squin.kernel
def runtime_allocation_length(size: int):
    qs = squin.qalloc(size)
    return len(qs)


@pytest.mark.parametrize("size", [0, 1, 3])
def test_allocation_sizes_survive_the_jeff_file_roundtrip(size):
    restored = returned(runtime_allocation_length)
    assert simulate(restored, size) == simulate(runtime_allocation_length, size) == size


def test_jeff_export_rejects_a_negative_constant_allocation():
    with rejected("allocation size must be nonnegative"):
        SquinToJeff().emit(negative_allocation_length)
