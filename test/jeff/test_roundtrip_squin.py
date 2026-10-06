"""Tests that a squin kernel survives the trip to jeff, to a file, and back to squin."""

import math
import tempfile
from typing import Any
from pathlib import Path

import pytest
from kirin import ir
from kirin.dialects import math as kmath, ilist
from kirin.dialects.ilist import IList

from bloqade import squin
from bloqade.jeff import JeffToSquin, SquinToJeff, emit_jeff, load_jeff
from bloqade.types import Qubit, MeasurementResult
from bloqade.squin.gate import _interface as gate

from .build import validate
from .helpers import simulate, as_python


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
def logic(a: int, b: int, x: float):
    # Python's `and` and `or` return an operand, so `not` compares truth values.
    return [not a, not (a and b), not (a or b), not x, not (x and b)]


DETERMINISTIC = [
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
]

# pyqrack has no rule for `is_zero` on the squin source, so this one skips it.
DETERMINISTIC_AFTER_THE_TRIP = [*DETERMINISTIC, (inverted, (1,), [1, 0])]


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
