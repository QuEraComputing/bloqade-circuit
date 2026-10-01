"""Converting jeff dialect IR to squin: coverage, semantics, and the throw
validation for constructs squin cannot express."""

import math

import pytest
from kirin import ir, types
from kirin.dialects import py, scf, func, ilist
from kirin.validation import ValidationSuite

from bloqade import jeff
from bloqade.jeff import JeffToSquin
from bloqade.types import MeasurementResultType
from bloqade.pyqrack import StackMemorySimulator, DynamicMemorySimulator
from bloqade.jeff.types import qureg
from bloqade.jeff.dialects import stmts
from bloqade.jeff.analysis.validation import JeffToSquinValidation

from . import test_roundtrip as tr
from .build import add, entry, method, switch, for_loop, validate
from .helpers import rejected, simulate, as_python, one_wire_program

# every roundtrip kernel except the while loop, which squin cannot express


CONVERTIBLE = [k for k in tr.KERNELS if k is not tr.rus]


@pytest.mark.parametrize("build", CONVERTIBLE, ids=lambda f: f.__name__)
def test_converts_and_verifies(build):
    converted = JeffToSquin().emit(build())
    converted.verify()  # valid squin IR on the squin.kernel group


def test_bell_converts_to_expected_gates():
    converted = JeffToSquin().emit(tr.bell())
    names = [
        n.name
        for n in converted.callable_region.walk()
        if n.dialect is not None and n.dialect.name in ("qubit", "squin.gate")
    ]
    assert names == ["new", "new", "h", "cx", "measure", "measure"]


def test_converted_bell_is_typed():
    """The declared output is what squin infers: a list of measurement results,
    not the bit type jeff gave the array."""
    converted = JeffToSquin().emit(tr.bell())
    assert converted.code.signature.output.is_subseteq(
        ilist.IListType[MeasurementResultType, types.Any]
    )


def test_converted_bell_simulates_correlated():
    # a jeff bell returning the two bits as a tuple (a shape pyqrack returns)
    block, _ = entry()
    w0 = add(block, stmts.Alloc()).result
    w1 = add(block, stmts.Alloc()).result
    w0 = add(block, stmts.Gate((w0,), (), (), gate_name="h")).results[0]
    cx = add(block, stmts.Gate((w1,), (w0,), (), gate_name="x"))
    m0 = add(block, stmts.MeasureNd(cx.results[0]))
    m1 = add(block, stmts.MeasureNd(cx.results[1]))
    add(block, stmts.Free(m0.result_wire))
    add(block, stmts.Free(m1.result_wire))
    add(block, stmts.Return(m0.bit, m1.bit))
    code = func.Function(
        sym_name="bell2",
        body=ir.Region(block),
        signature=func.Signature(inputs=(), output=types.Any),
    )
    converted = JeffToSquin().emit(
        ir.Method(dialects=jeff.kernel, code=code, sym_name="bell2")
    )

    sim = StackMemorySimulator(min_qubits=2)
    shots = [sim.run(converted) for _ in range(30)]
    assert all(int(a) == int(b) for a, b in shots)


def test_three_way_switch_converts_to_nested_ifs():
    block, [sel] = entry(types.Int)
    w = add(block, stmts.Alloc()).result
    sw = switch(
        block,
        sel,
        (w,),
        cases=[
            lambda b, x: (add(b, stmts.Gate((x,), (), (), gate_name="h")).results[0],),
            lambda b, x: (add(b, stmts.Gate((x,), (), (), gate_name="x")).results[0],),
        ],
        default=lambda b, x: (
            add(b, stmts.Gate((x,), (), (), gate_name="z")).results[0],
        ),
    )
    m = add(block, stmts.MeasureNd(sw.results[0]))
    add(block, stmts.Free(m.result_wire))
    converted = JeffToSquin().emit(
        method(block, m.bit, types.Bool, inputs=(types.Int,), name="three")
    )
    converted.verify()

    ifs = [n for n in converted.callable_region.walk() if isinstance(n, scf.IfElse)]
    assert len(ifs) == 2  # 3-way switch -> two nested if/else


def _classical(build):
    """A jeff function of two ints returning what `build` computes from them."""
    block, [a, b] = entry(types.Int, types.Int)
    out = build(block, a, b)
    pair = types.Generic(tuple, *(types.Int for _ in out))
    return JeffToSquin().emit(method(block, out, pair, inputs=(types.Int, types.Int)))


@pytest.mark.parametrize("a, b", [(7, 2), (-7, 2), (7, -2), (-7, -2), (6, -3)])
def test_signed_division_truncates_toward_zero(a, b):
    """`divS` and `remS` follow the convention every IR naming them so does:
    the quotient truncates and the remainder is signed like the dividend."""

    def divide(block, x, y):
        return [
            add(block, stmts.IntDivS(x, y)).result,
            add(block, stmts.IntRemS(x, y)).result,
        ]

    quotient, remainder = StackMemorySimulator().run(_classical(divide), args=(a, b))
    assert quotient == int(a / b) and remainder == a - b * int(a / b)


@pytest.mark.parametrize("a, b", [(3, 5), (5, 3), (-2, 2)])
def test_min_and_max_convert_to_conditionals(a, b):
    def extrema(block, x, y):
        return [
            add(block, stmts.IntMinS(x, y)).result,
            add(block, stmts.IntMaxS(x, y)).result,
        ]

    assert tuple(StackMemorySimulator().run(_classical(extrema), args=(a, b))) == (
        min(a, b),
        max(a, b),
    )


def test_mutable_array_rejected():
    # squin's lists are immutable, so a filled-in-place array has no squin form
    block, [n] = entry(types.Int)
    arr = add(block, stmts.IntArrayZero(n)).result
    idx = add(block, stmts.ConstInt(value=0)).result
    w = add(block, stmts.Alloc()).result
    m = add(block, stmts.MeasureNd(w))
    add(block, stmts.Free(m.result_wire))
    arr = add(block, stmts.IntArraySet(arr, idx, m.bit)).result
    with rejected("mutable array"):
        JeffToSquin().emit(
            method(block, arr, jeff.IntArrayType, inputs=(types.Int,), name="acc")
        )


def test_while_rejected():
    with rejected("while"):
        JeffToSquin().emit(tr.rus())


def test_ppr_rejected():
    def fill(block, w):
        angle = add(block, stmts.ConstFloat(value=0.5)).result
        ppr = add(block, stmts.Ppr((w,), (), angle, pauli_string=("z",)))
        return ppr.results[0]

    with rejected("Pauli-product"):
        JeffToSquin().emit(one_wire_program(fill))


def test_unknown_gate_rejected():
    def fill(block, w):
        return add(block, stmts.Gate((w,), (), (), gate_name="bogus")).results[0]

    with rejected("bogus"):
        JeffToSquin().emit(one_wire_program(fill))


def test_controlled_rotation_rejected():
    # squin has no controlled rotation; the conversion maps gates one to one and
    # does not decompose
    def fill(block, w):
        c = add(block, stmts.Alloc()).result
        angle = add(block, stmts.ConstFloat(value=0.5)).result
        t, c = add(block, stmts.Gate((w,), (c,), (angle,), gate_name="rz")).results
        add(block, stmts.Free(c))
        return t

    with rejected("rz with 1 controls"):
        JeffToSquin().emit(one_wire_program(fill))


def _returned(mt: ir.Method) -> int:
    """Return how many values the converted squin form of `mt` returns."""
    (ret,) = [
        n
        for n in JeffToSquin().emit(mt).callable_region.walk()
        if isinstance(n, func.Return)
    ]
    match ret.value.owner:
        case func.ConstantNone():
            return 0
        case py.tuple.New(args=members):
            return len(members)
    return 1


def test_every_output_is_returned_through_a_gate_and_a_loop():
    """A function returning (bit, q0, q1) returns all three values. One wire
    passes through a gate and the other through a loop."""
    block, (q0, q1) = entry(jeff.WireType, jeff.WireType)
    gated = add(block, stmts.Gate((q0,), (), (), gate_name="h")).results[0]
    measured = add(block, stmts.MeasureNd(gated))
    lo = add(block, stmts.ConstInt(value=0)).result
    hi = add(block, stmts.ConstInt(value=2)).result
    one = add(block, stmts.ConstInt(value=1)).result
    loop = for_loop(
        block,
        lo,
        hi,
        one,
        (q1,),
        lambda b, i, s: (add(b, stmts.Gate((s,), (), (), gate_name="x")).results[0],),
    )
    mt = method(
        block,
        (measured.bit, measured.result_wire, loop.results[0]),
        types.Generic(tuple, types.Bool, jeff.WireType, jeff.WireType),
    )
    assert _returned(mt) == 3


def test_a_wire_through_a_switch_is_returned_and_the_caller_reads_it():
    """A callee flips a wire in one branch and passes it through the other.
    The caller reads the bit and the wire from the callee's tuple."""
    block, (w0, w1, c) = entry(jeff.WireType, jeff.WireType, types.Bool)
    picked = switch(
        block,
        c,
        (w1,),
        [lambda b, s: (s,)],
        lambda b, s: (add(b, stmts.Gate((s,), (), (), gate_name="x")).results[0],),
    )
    bit = add(block, stmts.Measure(w0)).bit
    callee = method(
        block,
        (bit, picked.results[0]),
        types.Generic(tuple, types.Bool, jeff.WireType),
        inputs=(jeff.WireType, jeff.WireType, types.Bool),
        name="flip_second_if",
    )
    assert _returned(callee) == 2

    outer, _ = entry()
    a = add(outer, stmts.Alloc()).result
    b = add(outer, stmts.Alloc()).result
    flag = add(outer, stmts.ConstInt(value=1, bitwidth=1)).result
    call = add(outer, stmts.Call(callee, (a, b, flag), (types.Bool, jeff.WireType)))
    measured = add(outer, stmts.MeasureNd(call.results[1]))
    add(outer, stmts.Free(measured.result_wire))
    mt = method(
        outer,
        (call.results[0], measured.bit),
        types.Generic(tuple, types.Bool, types.Bool),
    )
    validate(mt)
    converted = JeffToSquin().emit(mt)

    assert as_python(DynamicMemorySimulator().run(converted)) == (0, 1)


def test_a_swapped_return_binds_each_output_to_the_wire_it_returns():
    """`swap_back(a, b)` returns `(b, a)`, so the caller's first output is `b`."""
    block, (a, b) = entry(jeff.WireType, jeff.WireType)
    callee = method(
        block,
        (b, a),
        types.Generic(tuple, jeff.WireType, jeff.WireType),
        inputs=(jeff.WireType, jeff.WireType),
        name="swap_back",
    )
    assert _returned(callee) == 2
    outer, _ = entry()
    p = add(outer, stmts.Alloc()).result
    q = add(outer, stmts.Alloc()).result
    p = add(outer, stmts.Gate((p,), (), (), gate_name="x")).results[0]
    call = add(outer, stmts.Call(callee, (p, q), (jeff.WireType, jeff.WireType)))
    first = add(outer, stmts.MeasureNd(call.results[0]))
    second = add(outer, stmts.MeasureNd(call.results[1]))
    add(outer, stmts.Free(first.result_wire))
    add(outer, stmts.Free(second.result_wire))
    mt = method(
        outer, (first.bit, second.bit), types.Generic(tuple, types.Bool, types.Bool)
    )
    validate(mt)
    assert as_python(simulate(JeffToSquin().emit(mt))) == (0, 1)


def test_conversion_state_is_local_to_one_emission():
    """A converter reused on a changed method converts what it sees now."""
    conversion = JeffToSquin()
    block, _ = entry()
    value = add(block, stmts.ConstInt(value=1))
    mt = method(block, value.result, types.Int)
    assert conversion.emit(mt).callable_region.blocks[0].first_stmt.value.unwrap() == 1
    value.value = 2
    assert conversion.emit(mt).callable_region.blocks[0].first_stmt.value.unwrap() == 2


def _values(build, kinds):
    block, _ = entry()
    values = build(block)
    return method(block, values, types.Generic(tuple, *kinds))


def test_signed_division_rounds_toward_zero():
    def build(block):
        def c(v):
            return add(block, stmts.ConstInt(value=v)).result

        return (
            add(block, stmts.IntDivS(c(-7), c(2))).result,
            add(block, stmts.IntRemS(c(-7), c(2))).result,
            add(block, stmts.IntDivS(c(7), c(-2))).result,
            add(block, stmts.IntRemS(c(7), c(-2))).result,
        )

    converted = JeffToSquin().emit(_values(build, [types.Int] * 4))
    assert as_python(simulate(converted)) == (-3, -1, -3, 1)


def test_refuses_an_unsigned_integer_operation():
    block, _ = entry()
    one = add(block, stmts.ConstInt(value=1)).result
    quotient = add(block, stmts.IntDivU(one, one)).result
    with rejected("have no unsigned form for 'int_div_u'"):
        JeffToSquin().emit(method(block, quotient, types.Int))


def test_float_min_max_log_convert():
    def build(block):
        def c(v):
            return add(block, stmts.ConstFloat(value=v)).result

        return (
            add(block, stmts.FloatMin(c(2.0), c(0.5))).result,
            add(block, stmts.FloatMax(c(2.0), c(0.5))).result,
            add(block, stmts.FloatLog(c(math.e))).result,
        )

    converted = JeffToSquin().emit(_values(build, [types.Float] * 3))
    least, most, log = simulate(converted)  # floats, read as they are
    assert (least, most) == (0.5, 2.0) and abs(log - 1.0) < 1e-12


def test_sxdg_identity_and_default_only_switch_convert():
    """`sxdg` is the adjoint of sqrt_x under its alias; `i` applies as
    nothing; a switch with only a default takes it."""
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    w = add(block, stmts.Gate((w,), (), (), gate_name="x")).results[0]
    w = add(block, stmts.Gate((w,), (), (), gate_name="sx")).results[0]
    w = add(block, stmts.Gate((w,), (), (), gate_name="sxdg")).results[0]
    w = add(block, stmts.Gate((w,), (), (), gate_name="i")).results[0]
    two = add(block, stmts.ConstInt(value=2)).result
    picked = switch(
        block,
        two,
        (w,),
        [],
        lambda b, s: (add(b, stmts.Gate((s,), (), (), gate_name="x")).results[0],),
    )
    measured = add(block, stmts.MeasureNd(picked.results[0]))
    add(block, stmts.Free(measured.result_wire))
    converted = JeffToSquin().emit(method(block, measured.bit, types.Bool))
    assert as_python(simulate(converted)) == 0  # x, then the default's x


def test_a_register_with_a_replaced_slot_is_a_new_register():
    """A callee that frees a slot's qubit and inserts a fresh one returns a new
    list. The caller reads the callee's result."""
    block, (reg,) = entry(qureg(1))
    zero = add(block, stmts.ConstInt(value=0)).result
    taken = add(block, stmts.Extract(reg, zero))
    add(block, stmts.Free(taken.wire))
    fresh = add(block, stmts.Alloc()).result
    fresh = add(block, stmts.Gate((fresh,), (), (), gate_name="x")).results[0]
    replaced = add(block, stmts.Insert(taken.result_reg, zero, fresh)).result
    callee = method(block, replaced, qureg(1), inputs=(qureg(1),), name="replace")
    assert _returned(callee) == 1

    outer, _ = entry()
    size = add(outer, stmts.ConstInt(value=1)).result
    made = add(outer, stmts.RegAlloc(size)).result
    back = add(outer, stmts.Call(callee, (made,), (qureg(1),))).results[0]
    index = add(outer, stmts.ConstInt(value=0)).result
    got = add(outer, stmts.Extract(back, index))
    measured = add(outer, stmts.MeasureNd(got.wire))
    whole = add(outer, stmts.Insert(got.result_reg, index, measured.result_wire)).result
    add(outer, stmts.RegFree(whole))
    mt = method(outer, measured.bit, types.Bool)
    validate(mt)
    assert as_python(simulate(JeffToSquin().emit(mt))) == 1


@pytest.mark.skip(
    reason="kirin types a tuple member read at index 0 as a union until 0.23"
)
def test_a_qubit_at_tuple_position_zero_beside_a_classical_output():
    """A qubit at position 0 beside a classical output stays a qubit through the
    call's tuple read."""
    block, _ = entry()
    fresh = add(block, stmts.Alloc()).result
    seven = add(block, stmts.ConstInt(value=7)).result
    callee = method(
        block,
        (fresh, seven),
        types.Generic(tuple, jeff.WireType, types.Int),
        name="make",
    )
    outer, _ = entry()
    call = add(outer, stmts.Call(callee, (), (jeff.WireType, types.Int)))
    measured = add(outer, stmts.MeasureNd(call.results[0]))
    add(outer, stmts.Free(measured.result_wire))
    mt = method(
        outer,
        (measured.bit, call.results[1]),
        types.Generic(tuple, types.Bool, types.Int),
    )
    assert as_python(simulate(JeffToSquin().emit(mt))) == (0, 7)


def test_global_phase_applies_as_nothing():
    """An uncontrolled global phase, as MQT Core's export leaves behind when
    it merges rotations, is unobservable; a controlled one is a real gate."""
    block, _ = entry()
    w = add(
        block,
        stmts.Gate((w := add(block, stmts.Alloc()).result,), (), (), gate_name="x"),
    ).results[0]
    angle = add(block, stmts.ConstFloat(value=0.7)).result
    add(block, stmts.Gate((), (), (angle,), gate_name="gphase"))
    measured = add(block, stmts.MeasureNd(w))
    add(block, stmts.Free(measured.result_wire))
    converted = JeffToSquin().emit(method(block, measured.bit, types.Bool))
    assert as_python(simulate(converted)) == 1

    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    angle = add(block, stmts.ConstFloat(value=0.7)).result
    add(block, stmts.Gate((), (w,), (angle,), gate_name="gphase"))
    with rejected("gphase"):
        JeffToSquin().emit(method(block, None, types.NoneType))


@pytest.mark.parametrize(
    "name, targets, params",
    [("h", 2, 0), ("rx", 1, 0), ("swap", 1, 0), ("u", 1, 1)],
)
def test_refuses_a_gate_with_the_wrong_arity(name, targets, params):
    block, _ = entry()
    wires = [add(block, stmts.Alloc()).result for _ in range(targets)]
    angles = [add(block, stmts.ConstFloat(value=0.5)).result for _ in range(params)]
    gate = add(block, stmts.Gate(tuple(wires), (), tuple(angles), gate_name=name))
    for wire in gate.results:
        add(block, stmts.Free(wire))
    with rejected(f"gate '{name}' has no squin statement"):
        JeffToSquin().emit(method(block, None, types.NoneType))


def test_the_validation_suite_runs_the_conversion_validation_on_its_own():
    block, (w,) = entry(jeff.WireType)
    angle = add(block, stmts.ConstFloat(value=0.5)).result
    ppr = add(block, stmts.Ppr((w,), (), angle, pauli_string=("z",)))
    mt = method(block, (ppr.results[0],), jeff.WireType, inputs=(jeff.WireType,))
    result = ValidationSuite([JeffToSquinValidation]).validate(mt)
    messages = [str(error) for error in result.errors["JeffToSquin"]]
    assert any("Pauli-product rotation" in m for m in messages)


@pytest.mark.parametrize("a, b", [(True, True), (True, False), (False, False)])
def test_a_negated_bit_operation_stays_a_logical_not(a, b):
    """A bit from a rewritten statement keeps its type, so `int_not` becomes `not`."""
    block, [x, y] = entry(types.Bool, types.Bool)
    both = add(block, stmts.IntAnd(x, y))
    both.result.type = types.Bool
    negated = add(block, stmts.IntNot(both.result))
    negated.result.type = types.Bool
    converted = JeffToSquin().emit(
        method(block, negated.result, types.Bool, inputs=(types.Bool, types.Bool))
    )
    assert StackMemorySimulator().run(converted, args=(a, b)) == (not (a and b))
