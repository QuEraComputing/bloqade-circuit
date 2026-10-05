"""Tests of the conversion from squin kernels to jeff dialect IR."""

from typing import Any

import pytest
from kirin import ir, types
from kirin.dialects import ilist
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.qubit import _interface as qstmt
from bloqade.types import Qubit, MeasurementResult
from bloqade.jeff.types import WireType, QuregType
from bloqade.jeff.dialects import stmts
from bloqade.jeff.squin2jeff import SquinToJeff, SquinToJeffValidation

from .build import validate
from .helpers import roundtrips


def converted(kernel: ir.Method) -> ir.Method:
    """Convert `kernel`, check the jeff result and its file round trip."""
    result = SquinToJeff().emit(kernel)
    result.verify()
    validate(result)
    assert roundtrips(result)
    return result


def statements(mt: ir.Method, kind: type[ir.Statement]) -> list[ir.Statement]:
    return [s for s in mt.callable_region.walk() if isinstance(s, kind)]


def gate_names(mt: ir.Method) -> list[str]:
    return [s.gate_name for s in statements(mt, stmts.Gate)]


def refused(kernel: ir.Method, reason: str) -> None:
    """Check that the conversion refuses `kernel` and names `reason`."""
    with pytest.raises(ValidationErrorGroup) as caught:
        SquinToJeff().emit(kernel)
    assert any(reason in str(error) for error in caught.value.errors)


# -- kernels -------------------------------------------------------------------


@squin.kernel
def bell() -> MeasurementResult:
    a = squin.qubit.new()
    b = squin.qubit.new()
    squin.h(a)
    squin.cx(a, b)
    m = squin.measure(a)
    return m


@squin.kernel
def flip(q: Qubit) -> Qubit:
    squin.x(q)
    return q


@squin.kernel
def fresh() -> Qubit:
    q = squin.qubit.new()
    squin.h(q)
    return q


@squin.kernel
def register(n: int, i: int) -> None:
    qs = squin.qalloc(n)
    squin.h(qs[0])
    squin.cx(qs[i], qs[1])


@squin.kernel
def loop(n: int) -> int:
    q = squin.qubit.new()
    qs = squin.qalloc(n)
    total = 0
    for k in range(n):
        squin.cx(q, qs[k])
        total = total + k
    return total


@squin.kernel
def branch(q: Qubit, flag: bool) -> int:
    count = 0
    if flag:
        squin.x(q)
        count = 1
    return count


@squin.kernel
def calls(q: Qubit) -> MeasurementResult:
    flip(q)
    a = fresh()
    squin.cx(a, q)
    return squin.measure(a)


@squin.kernel
def flips_twice(q: Qubit) -> None:
    squin.x(q)
    squin.x(q)


@squin.kernel
def chained() -> MeasurementResult:
    q = squin.qubit.new()
    flips_twice(q)
    flip(q)
    return squin.measure(q)


@squin.kernel
def rotated(theta: float) -> None:
    q = squin.qubit.new()
    squin.rx(theta, q)
    squin.rz(0.25, q)


@squin.kernel
def counted(n: int) -> int:
    qs = squin.qalloc(n)
    total = 0
    for k in range(1, n, 2):
        squin.h(qs[k])
        total = total + k * 2
    return total


@squin.kernel
def wrapped(flag: bool) -> ilist.IList[bool, Any]:
    q = qstmt.new()
    qstmt.reset([q])
    bits = qstmt.measure([q])
    zeros = qstmt.is_zero(bits)
    return qstmt.is_one(zeros)


# -- conversions ---------------------------------------------------------------


def test_the_qubit_statement_wrappers_convert():
    mt = converted(wrapped)
    assert len(statements(mt, stmts.Alloc)) == 1
    assert len(statements(mt, stmts.Reset)) == 1
    assert len(statements(mt, stmts.MeasureNd)) == 1
    assert len(statements(mt, stmts.IntNot)) == 1


def test_emit_takes_a_squin_kernel_only():
    with pytest.raises(ValueError, match="squin.kernel"):
        SquinToJeff().emit(SquinToJeff().emit(flip))


def test_bell_allocates_gates_measures_and_frees():
    mt = converted(bell)
    assert len(statements(mt, stmts.Alloc)) == 2
    assert gate_names(mt) == ["h", "x"]
    (gate,) = [s for s in statements(mt, stmts.Gate) if s.gate_name == "x"]
    assert len(gate.controls) == 1 and len(gate.targets) == 1
    (measured,) = statements(mt, stmts.MeasureNd)
    assert len(statements(mt, stmts.Free)) == 2
    (returned,) = statements(mt, stmts.Return)
    assert returned.values == (measured.bit,)
    assert mt.return_type == types.Bool


def test_a_register_is_extracted_and_inserted_at_each_slot():
    mt = converted(register)
    (allocation,) = statements(mt, stmts.RegAlloc)
    assert allocation.size is mt.callable_region.blocks[0].args[1]
    extracts = statements(mt, stmts.Extract)
    inserts = statements(mt, stmts.Insert)
    assert len(extracts) == 3 and len(inserts) == 3
    index = mt.callable_region.blocks[0].args[2]
    assert [e.index is index for e in extracts] == [i.index is index for i in inserts]
    assert sum(e.index is index for e in extracts) == 1
    assert gate_names(mt) == ["h", "x"]
    assert len(statements(mt, stmts.RegFree)) == 1


def test_a_loop_carries_the_wires_and_the_classical_state():
    mt = converted(loop)
    (loop_stmt,) = statements(mt, stmts.For)
    kinds = [value.type for value in loop_stmt.state]
    assert [k.is_subseteq(WireType) or k.is_subseteq(QuregType) for k in kinds].count(
        True
    ) == 2
    assert gate_names(mt) == ["x"]
    assert [s.name for s in statements(mt, stmts.IntBinary)] == ["int_add"]
    body = loop_stmt.body.blocks[0]
    assert isinstance(body.last_stmt, stmts.Yield)
    assert len(body.last_stmt.values) == len(loop_stmt.state)


def test_a_range_with_bounds_gives_the_loop_bounds():
    mt = converted(counted)
    (loop_stmt,) = statements(mt, stmts.For)
    start, step = loop_stmt.start.owner, loop_stmt.step.owner
    assert isinstance(start, stmts.ConstInt) and start.value == 1
    assert isinstance(step, stmts.ConstInt) and step.value == 2
    assert loop_stmt.stop is mt.callable_region.blocks[0].args[1]


def test_a_branch_becomes_a_switch_with_the_else_as_case_zero():
    mt = converted(branch)
    (switch,) = statements(mt, stmts.Switch)
    assert switch.selector is mt.callable_region.blocks[0].args[2]
    assert len(switch.branches) == 1
    assert gate_names(mt) == ["x"]
    assert switch.default.blocks[0].stmts.at(0) is not None
    (returned,) = statements(mt, stmts.Return)
    assert all(value in switch.results for value in returned.values)


def test_a_callee_hands_its_parameters_back_first():
    mt = converted(calls)
    flip_call, fresh_call = statements(mt, stmts.Call)
    assert flip_call.callee.sym_name == "fresh" or fresh_call.callee.sym_name == "fresh"
    calls_by_name = {c.callee.sym_name: c for c in (flip_call, fresh_call)}
    assert calls_by_name["flip"].callee.return_type == WireType
    assert calls_by_name["fresh"].callee.return_type == WireType
    assert len(calls_by_name["flip"].results) == 1
    (gate,) = [s for s in statements(mt, stmts.Gate) if s.gate_name == "x"]
    assert gate.controls[0] is calls_by_name["fresh"].results[0]
    assert gate.targets[0] is calls_by_name["flip"].results[0]


def test_a_callee_that_returns_none_hands_its_wire_back():
    mt = converted(chained)
    calls = statements(mt, stmts.Call)
    assert [c.callee.sym_name for c in calls] == ["flips_twice", "flip"]
    assert all(len(c.results) == 1 for c in calls)
    (returned,) = statements(mt, stmts.Return)
    assert len(returned.values) == 1


def test_a_rotation_keeps_its_radians():
    mt = converted(rotated)
    rx, rz = statements(mt, stmts.Gate)
    assert rx.params[0] is mt.callable_region.blocks[0].args[1]
    assert isinstance(constant := rz.params[0].owner, stmts.ConstFloat)
    assert constant.value == 0.25


def test_a_measurement_is_a_bit_in_a_switch():
    @squin.kernel
    def measured() -> None:
        q = squin.qubit.new()
        if squin.measure(q):
            squin.x(q)

    mt = converted(measured)
    (measured_stmt,) = statements(mt, stmts.MeasureNd)
    (switch,) = statements(mt, stmts.Switch)
    assert switch.selector is measured_stmt.bit


def test_the_validation_pass_runs_on_its_own():
    _, errors = SquinToJeffValidation().run(bell)
    assert errors == []


@squin.kernel
def truth(a: int, b: int, x: float, f: bool, g: bool):
    return [not a, a and b, a or b, not x, f and g, not f]


def _zero_test(value: ir.SSAValue, of: ir.SSAValue) -> bool:
    """Return True if `value` is jeff's test that `of` equals zero."""
    test = value.owner
    return (
        isinstance(test, (stmts.IntEq, stmts.FloatEq))
        and test.lhs is of
        and isinstance(test.rhs.owner, (stmts.ConstInt, stmts.ConstFloat))
        and test.rhs.owner.value == 0
    )


def _truth_bit(value: ir.SSAValue, of: ir.SSAValue) -> bool:
    """Return True if `value` is the negation of jeff's zero test of `of`."""
    negation = value.owner
    return isinstance(negation, stmts.IntNot) and _zero_test(negation.value, of)


def test_not_and_or_take_the_truth_of_a_number():
    mt = converted(truth)
    a, b, x, f, g = mt.callable_region.blocks[0].args[1:]
    (created,) = statements(mt, stmts.IntArrayCreate)
    not_a, a_and_b, a_or_b, not_x, f_and_g, not_f = created.values
    assert _zero_test(not_a, a)
    assert _zero_test(not_x, x)
    for value, kind in ((a_and_b, stmts.IntAnd), (a_or_b, stmts.IntOr)):
        assert isinstance(value.owner, kind)
        assert _truth_bit(value.owner.lhs, a) and _truth_bit(value.owner.rhs, b)
    # Two bools need no zero test.
    assert isinstance(f_and_g.owner, stmts.IntAnd)
    assert (f_and_g.owner.lhs, f_and_g.owner.rhs) == (f, g)
    assert isinstance(not_f.owner, stmts.IntNot) and not_f.owner.value is f


@squin.kernel
def number_then_qubit(q: Qubit):
    squin.x(q)
    return (1, q)


@squin.kernel
def forwarded(q: Qubit):
    pair = number_then_qubit(q)
    return pair


def test_a_forwarded_tuple_is_checked_at_each_position():
    mt = converted(forwarded)
    (call,) = statements(mt, stmts.Call)
    (returned,) = statements(mt, stmts.Return)
    assert returned.values == tuple(call.results)


def test_one_validation_checks_two_kernels_in_turn():
    validation = SquinToJeffValidation()
    for kernel in (bell, forwarded):
        _, errors = validation.run(kernel)
        assert errors == []


# -- refusals ------------------------------------------------------------------


@squin.kernel
def negated_bool(flag: bool) -> int:
    return -flag


@squin.kernel
def inverted_bool(flag: bool) -> int:
    return ~flag


@squin.kernel
def from_the_end(n: int) -> None:
    qs = squin.qalloc(n)
    squin.h(qs[-1])


@squin.kernel
def register_and_qubit(qs: ilist.IList[Qubit, Any], q: Qubit) -> None:
    squin.x(q)
    squin.h(qs[1])


@squin.kernel
def register_and_its_slot():
    qs = squin.qalloc(2)
    register_and_qubit(qs, qs[0])


@squin.kernel
def twice(q: Qubit) -> None:
    squin.cx(q, q)


@squin.kernel
def sliced(qs: ilist.IList[Qubit, Any]) -> None:
    squin.h(qs[0:2][0])


@squin.kernel
def escaped(n: int) -> None:
    q = squin.qubit.new()
    for _ in range(n):
        q = squin.qubit.new()
    squin.h(q)


@squin.kernel
def noisy(q: Qubit) -> None:
    squin.depolarize(0.1, q)


@squin.kernel
def broadcast(qs: ilist.IList[Qubit, Any]) -> None:
    squin.broadcast.h(qs)


@squin.kernel
def slot(qs: ilist.IList[Qubit, Any]) -> Qubit:
    return qs[0]


@squin.kernel
def listed(a: Qubit, b: Qubit) -> None:
    squin.broadcast.h([a, b])


@squin.kernel
def divided(x: float, y: float) -> float:
    return x / y


@squin.kernel
def both(a: Qubit, b: Qubit) -> None:
    squin.h(a)
    squin.h(b)


@squin.kernel
def passes_twice(q: Qubit) -> None:
    both(q, q)


@squin.kernel
def concatenated(n: int) -> int:
    both = [n, 2] + [3]
    return both[0]


@squin.kernel
def mistyped() -> bool:
    q = squin.qubit.new()
    return squin.measure(q)


@squin.kernel
def nested() -> None:
    q = squin.qubit.new()

    def flips(t: Qubit) -> None:
        squin.x(t)

    flips(q)


@squin.kernel
def mixed(x: float, k: int) -> float:
    return x * k


@squin.kernel
def uneven(a: Qubit, b: Qubit, c: Qubit) -> None:
    squin.broadcast.cx([a], [b, c])


@squin.kernel
def unsized_not(n: int) -> ilist.IList[bool, Any]:
    qs = squin.qalloc(n)
    return squin.broadcast.is_zero(squin.broadcast.measure(qs))


@squin.kernel
def tuple_in_loop(n: int) -> int:
    pair = (n, 1)
    total = 0
    for _ in range(n):
        total = total + pair[0]
    return total


@squin.kernel
def tuple_from_branch(flag: bool) -> int:
    if flag:
        pair = (1, 2)
    else:
        pair = (3, 4)
    return pair[0]


@squin.kernel
def returns_qubits(a: Qubit, b: Qubit) -> ilist.IList[Qubit, Any]:
    return [a, b]


@squin.kernel
def takes_tuple(pair: tuple[int, int]) -> int:
    return pair[0]


@squin.kernel
def passes_tuple(n: int) -> int:
    return takes_tuple((n, n))


@squin.kernel
def over_list(qs: ilist.IList[Qubit, Any]) -> None:
    for q in qs:
        squin.h(q)


@squin.kernel
def tuple_at_runtime(n: int, k: int) -> int:
    pair = (n, 1)
    return pair[k]


@pytest.mark.parametrize(
    "kernel, reason",
    [
        (twice, "'cx' takes one qubit twice"),
        (passes_twice, "'both' takes one qubit twice"),
        (concatenated, "passed to 'add'"),
        (mistyped, "left as `Bottom`"),
        (nested, "defined inside a kernel"),
        (mixed, "an integer mixed with a float"),
        (uneven, "qubit lists of different lengths"),
        (unsized_not, "a negation of a list of bits of unknown length"),
        (tuple_in_loop, "a result of type"),
        (tuple_from_branch, "a result of type"),
        (returns_qubits, "a function that returns a list of qubits"),
        (passes_tuple, "passed to a call"),
        (over_list, "a loop over a value that is not a range"),
        (tuple_at_runtime, "a tuple read at a runtime index"),
        (sliced, "a slice of a register"),
        (escaped, "a value carried by a loop or branch"),
        (noisy, "jeff has no form for 'depolarize'"),
        (broadcast, "register of known length"),
        (slot, "a function that returns one qubit of a register"),
        (divided, "jeff has no form for 'div'"),
        (negated_bool, "'usub' on a bool"),
        (register_and_its_slot, "'register_and_qubit' takes one qubit twice"),
        (from_the_end, "a negative index into a register of unknown length"),
        (inverted_bool, "'invert' on a bool"),
    ],
    ids=lambda x: x if isinstance(x, str) else x.sym_name,
)
def test_refusals(kernel, reason):
    refused(kernel, reason)


def test_a_literal_list_converts_to_gates_on_each_item():
    mt = converted(listed)
    assert gate_names(mt) == ["h", "h"]


@squin.kernel
def pair() -> tuple[Qubit, MeasurementResult]:
    q = squin.qubit.new()
    m = squin.measure(q)
    return q, m


@squin.kernel
def uses_pair() -> MeasurementResult:
    made = pair()
    squin.h(made[0])
    return made[1]


def test_a_returned_qubit_and_bit_become_two_outputs():
    mt = converted(uses_pair)
    (call,) = statements(mt, stmts.Call)
    assert [r.type for r in call.results] == [WireType, types.Bool]
    (gate,) = statements(mt, stmts.Gate)
    assert gate.targets[0] is call.results[0]
    (returned,) = statements(mt, stmts.Return)
    assert returned.values == (call.results[1],)


@squin.kernel
def bits_in_loop(n: int) -> None:
    q = squin.qubit.new()
    bits = squin.broadcast.measure([q])
    for _ in range(n):
        if bits[0]:
            squin.x(q)


def test_a_list_of_bits_is_a_bit_array_that_a_loop_carries():
    mt = converted(bits_in_loop)
    (created,) = statements(mt, stmts.IntArrayCreate)
    assert created.bitwidth == 1
    (loop_stmt,) = statements(mt, stmts.For)
    assert created.result in loop_stmt.state
    (read,) = statements(mt, stmts.IntArrayGet)
    assert read.bitwidth == 1
