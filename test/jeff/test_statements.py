"""Test the checks that each jeff statement runs on itself.

Kirin's `Method.verify` runs each statement's structure checks. `Method.verify_type`
runs each statement's type checks.
"""

import pytest
from kirin import ir, types

from bloqade import jeff
from bloqade.jeff.types import qureg
from bloqade.jeff.dialects import stmts

from .build import add, entry, method, switch, for_loop, while_loop


def check(mt: ir.Method) -> None:
    """Run kirin's structure checks and type checks on a method."""
    mt.verify()
    mt.verify_type()


def _measured(block):
    w = add(block, stmts.Alloc()).result
    m = add(block, stmts.MeasureNd(w))
    add(block, stmts.Free(m.result_wire))
    return m.bit


def _loop_over(block, w, body):
    lo = add(block, stmts.ConstInt(value=0)).result
    hi = add(block, stmts.ConstInt(value=2)).result
    one = add(block, stmts.ConstInt(value=1)).result
    return for_loop(block, lo, hi, one, (w,), body)


def _bit(block):
    return add(block, stmts.ConstInt(value=1, bitwidth=1)).result


def test_rejects_region_without_yield():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    lo = add(block, stmts.ConstInt(value=0)).result
    hi = add(block, stmts.ConstInt(value=1)).result
    one = add(block, stmts.ConstInt(value=1)).result
    body = ir.Block()
    body.args.append_from(types.Int, "i")
    wire = body.args.append_from(jeff.WireType, "w")
    # The body block ends without a yield.
    body.stmts.append(stmts.Gate((wire,), (), (), gate_name="h"))
    add(block, stmts.For(lo, hi, one, (w,), ir.Region(body)))
    with pytest.raises(ir.ValidationError, match="yield"):
        check(method(block, None, types.NoneType))


def test_rejects_for_arity_mismatch():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    lo = add(block, stmts.ConstInt(value=0)).result
    hi = add(block, stmts.ConstInt(value=1)).result
    one = add(block, stmts.ConstInt(value=1)).result
    body = ir.Block()
    body.args.append_from(types.Int, "i")
    wire = body.args.append_from(jeff.WireType, "w")
    # The body yields two values for one carried wire.
    body.stmts.append(stmts.Yield(wire, wire))
    add(block, stmts.For(lo, hi, one, (w,), ir.Region(body)))
    with pytest.raises(ir.ValidationError, match="yields 2 values"):
        check(method(block, None, types.NoneType))


def test_rejects_a_yield_of_another_family():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    lo = add(block, stmts.ConstInt(value=0)).result
    hi = add(block, stmts.ConstInt(value=2)).result
    one = add(block, stmts.ConstInt(value=1)).result

    def body(b, i, s):
        add(b, stmts.Free(s))
        # The body yields a bit for a wire.
        return (add(b, stmts.ConstInt(value=1, bitwidth=1)).result,)

    loop = for_loop(block, lo, hi, one, (w,), body)
    add(block, stmts.Free(loop.results[0]))
    with pytest.raises(ir.ValidationError, match="yields bool where Wire is carried"):
        check(method(block, None, types.NoneType))


def test_rejects_a_call_of_the_wrong_arity():
    callee_block, _ = entry()
    callee = method(callee_block, _measured(callee_block), types.Bool)
    block, _ = entry()
    extra = add(block, stmts.ConstInt(value=1)).result
    bit = add(block, stmts.Call(callee, (extra,), (types.Bool,))).results[0]
    with pytest.raises(ir.ValidationError, match="argument count"):
        check(method(block, bit, types.Bool))


def test_rejects_an_array_where_an_integer_is_taken():
    callee_block, (n,) = entry(types.Int)
    callee = method(callee_block, n, types.Int, inputs=(types.Int,))
    block, _ = entry()
    array = add(block, stmts.IntArrayConst(values=(1, 2), bitwidth=32)).result
    out = add(block, stmts.Call(callee, (array,), (types.Int,))).results[0]
    with pytest.raises(
        ir.ValidationError, match="passes IntArray where the callee takes int"
    ):
        check(method(block, out, types.Int))


def test_rejects_a_mistyped_region_argument():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    loop = _loop_over(block, w, lambda b, i, s: (s,))
    # The wire argument of the body now has type int.
    loop.body.blocks[0].args[1].type = types.Int
    add(block, stmts.Free(loop.results[0]))
    with pytest.raises(ir.ValidationError, match="takes int where Wire comes in"):
        check(method(block, None, types.NoneType))


def test_rejects_an_operand_of_the_wrong_type():
    block, _ = entry()
    bit = add(block, stmts.ConstInt(value=1, bitwidth=1)).result
    add(block, stmts.Free(bit))  # `Free` expects a wire and gets a bit.
    with pytest.raises(ir.ValidationError, match="Invalid type"):
        check(method(block, None, types.NoneType))


def test_rejects_a_register_typed_with_another_length():
    block, _ = entry()
    size = add(block, stmts.ConstInt(value=3)).result
    reg = add(block, stmts.RegAlloc(size))
    reg.result.type = qureg(5)
    add(block, stmts.RegFree(reg.result))
    with pytest.raises(ir.ValidationError, match="3 qubits is typed qureg\\[5\\]"):
        check(method(block, None, types.NoneType))


def test_rejects_a_constant_that_does_not_fit():
    block, _ = entry()
    big = add(block, stmts.ConstInt(value=2**40)).result
    with pytest.raises(ir.ValidationError, match="does not fit 32 bits"):
        check(method(block, big, types.Int))


def test_rejects_an_integer_result_of_a_bit_operation():
    block, _ = entry()
    a = add(block, stmts.ConstInt(value=1, bitwidth=1)).result
    # `IntAnd` types its result as an int by default.
    both = add(block, stmts.IntAnd(a, a))
    with pytest.raises(
        ir.ValidationError, match="an operation on bits must give a bit"
    ):
        check(method(block, both.result, types.Int))


def test_reports_a_region_without_a_block():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    lo = add(block, stmts.ConstInt(value=0)).result
    hi = add(block, stmts.ConstInt(value=2)).result
    one = add(block, stmts.ConstInt(value=1)).result
    loop = add(block, stmts.For(lo, hi, one, (w,), ir.Region()))
    add(block, stmts.Free(loop.results[0]))
    with pytest.raises(ir.ValidationError, match="must hold one block"):
        check(method(block, None, types.NoneType))


def test_rejects_a_return_of_another_count():
    block, _ = entry()
    bit = _measured(block)
    with pytest.raises(ir.ValidationError, match="declared number"):
        check(method(block, (bit, bit), types.Bool))


def test_rejects_a_return_of_another_family():
    block, _ = entry()
    bit = _measured(block)
    with pytest.raises(ir.ValidationError, match="gives bool where int is declared"):
        check(method(block, bit, types.Int))


def test_rejects_mixing_a_bit_with_an_integer():
    block, _ = entry()
    bit = _measured(block)
    one = add(block, stmts.ConstInt(value=1)).result
    total = add(block, stmts.IntAdd(bit, one)).result
    with pytest.raises(ir.ValidationError, match="mixes a bit with an integer"):
        check(method(block, total, types.Int))


def test_rejects_an_integer_result_of_not_on_a_bit():
    block, _ = entry()
    bit = _measured(block)
    # `IntNot` types its result as an int.
    negated = add(block, stmts.IntNot(bit)).result
    with pytest.raises(ir.ValidationError, match="'int_not' of a bit is a bit"):
        check(method(block, negated, types.Int))


def test_rejects_a_call_of_the_wrong_result_count():
    callee_block, _ = entry()
    callee = method(callee_block, _measured(callee_block), types.Bool)
    block, _ = entry()
    call = add(block, stmts.Call(callee, (), (types.Bool, types.Bool)))
    with pytest.raises(ir.ValidationError, match="result count"):
        check(method(block, call.results[0], types.Bool))


def test_rejects_a_while_condition_that_is_not_a_bit():
    block, _ = entry()
    zero = add(block, stmts.ConstInt(value=0)).result
    loop = while_loop(
        block,
        (zero,),
        lambda b, n: (n, n),  # The before region yields an int as the condition.
        lambda b, n: (n,),
    )
    with pytest.raises(ir.ValidationError, match="must yield a bit first"):
        check(method(block, loop.results[0], types.Int))


def test_rejects_a_branch_yielding_another_count():
    block, _ = entry()
    selector = add(block, stmts.ConstInt(value=0)).result
    one = add(block, stmts.ConstInt(value=1)).result
    picked = switch(block, selector, (one,), [lambda b, x: (x, x)], lambda b, x: (x,))
    with pytest.raises(ir.ValidationError, match="switch branch yields 2 values"):
        check(method(block, picked.results[0], types.Int))


def test_rejects_a_created_register_typed_with_another_length():
    block, _ = entry()
    a = add(block, stmts.Alloc()).result
    b = add(block, stmts.Alloc()).result
    reg = add(block, stmts.RegCreate((a, b))).result
    reg.type = qureg(5)
    add(block, stmts.RegFree(reg))
    with pytest.raises(ir.ValidationError, match=r"2 qubits is typed qureg\[5\]"):
        check(method(block, None, types.NoneType))


def test_rejects_a_loop_body_of_the_wrong_arity():
    block, _ = entry()
    lo = add(block, stmts.ConstInt(value=0)).result
    hi = add(block, stmts.ConstInt(value=2)).result
    one = add(block, stmts.ConstInt(value=1)).result
    w = add(block, stmts.Alloc()).result
    body = ir.Block()
    # The body has no argument for the carried wire.
    body.args.append_from(types.Int, "i")
    body.stmts.append(stmts.Yield(w))
    loop = add(block, stmts.For(lo, hi, one, (w,), ir.Region(body)))
    add(block, stmts.Free(loop.results[0]))
    with pytest.raises(ir.ValidationError, match="for-loop body arity mismatch"):
        check(method(block, None, types.NoneType))


def test_rejects_a_branch_of_the_wrong_arity():
    block, _ = entry()
    zero = add(block, stmts.ConstInt(value=0)).result
    one = add(block, stmts.ConstInt(value=1)).result
    # The branch has no argument for the input.
    branch = ir.Region(ir.Block([stmts.Yield(one)]))
    default = ir.Region(ir.Block([stmts.Yield(one)]))
    picked = add(block, stmts.Switch(zero, (one,), [branch], default))
    with pytest.raises(ir.ValidationError, match="switch branch arity mismatch"):
        check(method(block, picked.results[0], types.Int))


def test_rejects_a_while_after_region_of_the_wrong_shape():
    block, _ = entry()
    one = add(block, stmts.ConstInt(value=1)).result
    before = ir.Block()
    carried = before.args.append_from(types.Int, "in")
    bit = stmts.ConstInt(value=1, bitwidth=1)
    before.stmts.append(bit)
    before.stmts.append(stmts.Yield(bit.result, carried))
    # The after block has no argument and yields no value for the input.
    after = ir.Block([stmts.Yield()])
    loop = add(block, stmts.While((one,), ir.Region(before), ir.Region(after)))
    with pytest.raises(ir.ValidationError, match="while after-region"):
        check(method(block, loop.results[0], types.Int))


def test_rejects_a_call_result_of_another_family():
    callee_block, _ = entry()
    callee = method(callee_block, _measured(callee_block), types.Bool)
    block, _ = entry()
    out = add(block, stmts.Call(callee, (), (types.Int,))).results[0]
    with pytest.raises(
        ir.ValidationError, match="takes int where the callee returns bool"
    ):
        check(method(block, out, types.Int))


def test_rejects_a_while_before_region_yielding_too_little():
    block, _ = entry()
    one = add(block, stmts.ConstInt(value=1)).result
    loop = while_loop(block, (one,), lambda b, n: (n, n), lambda b, n: (n,))
    before = loop.before.blocks[0]
    terminator = before.last_stmt
    assert isinstance(terminator, stmts.Yield)
    # The new yield drops the condition and the output.
    terminator.replace_by(stmts.Yield())
    with pytest.raises(ir.ValidationError, match="while before-region yields"):
        check(method(block, loop.results[0], types.Int))


def test_a_specialized_rule_still_type_checks():
    """Kirin's type check rejects two floats before the bit-or-integer rule runs."""
    block, _ = entry()
    half = add(block, stmts.ConstFloat(value=0.5)).result
    total = add(block, stmts.IntAdd(half, half)).result
    with pytest.raises(ir.ValidationError, match="Invalid type"):
        check(method(block, total, types.Int))


def test_rejects_a_while_argument_of_another_family():
    block, _ = entry()
    one = add(block, stmts.ConstInt(value=1)).result
    before = ir.Block()
    taken = before.args.append_from(types.Float, "in")  # The loop input is an int.
    bit = stmts.ConstInt(value=1, bitwidth=1)
    before.stmts.append(bit)
    before.stmts.append(stmts.Yield(bit.result, taken))
    after = ir.Block()
    carried = after.args.append_from(types.Float, "out")
    after.stmts.append(stmts.Yield(carried))
    loop = add(block, stmts.While((one,), ir.Region(before), ir.Region(after)))
    with pytest.raises(ir.ValidationError, match="before-region takes float where int"):
        check(method(block, loop.results[0], types.Int))


def test_kirin_verify_checks_the_shape_of_a_loop():
    """Each region statement checks its own structure.

    Kirin's `Method.verify` therefore finds a malformed loop.
    """
    block, _ = entry()
    zero = add(block, stmts.ConstInt(value=0)).result
    body = ir.Block()
    body.args.append_from(types.Int, "i")
    # The loop carries nothing, and the body yields one value.
    body.stmts.append(stmts.Yield(zero))
    add(block, stmts.For(zero, zero, zero, (), ir.Region(body)))
    with pytest.raises(
        ir.ValidationError, match="for-loop body yields 1 values, expected 0"
    ):
        method(block, None, types.NoneType).verify()


def test_a_switch_over_wires_verifies():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    selector = add(block, stmts.ConstInt(value=1)).result

    def flip(b, wire):
        return add(b, stmts.Gate((wire,), (), (), gate_name="x")).results

    picked = switch(block, selector, (w,), [flip, lambda b, wire: (wire,)], flip)
    add(block, stmts.Free(picked.results[0]))
    mt = method(block, None, types.NoneType)
    check(mt)
    assert len(picked.branches) == 2


def test_rejects_a_switch_branch_yielding_another_family():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    selector = add(block, stmts.ConstInt(value=0)).result

    def measure(b, wire):
        m = add(b, stmts.MeasureNd(wire))
        add(b, stmts.Free(m.result_wire))
        return (m.bit,)

    def keep(b, wire):
        return (wire,)

    picked = switch(block, selector, (w,), [measure], keep)
    add(block, stmts.Free(picked.results[0]))
    with pytest.raises(
        ir.ValidationError, match="switch branch yields bool where Wire"
    ):
        check(method(block, None, types.NoneType))


def test_rejects_a_loop_index_that_is_not_an_integer():
    block, _ = entry()
    zero = add(block, stmts.ConstInt(value=0)).result
    body = ir.Block()
    body.args.append_from(types.Float, "i")
    body.stmts.append(stmts.Yield())
    add(block, stmts.For(zero, zero, zero, (), ir.Region(body)))
    with pytest.raises(ir.ValidationError, match="for-loop index is float"):
        check(method(block, None, types.NoneType))


def test_rejects_a_while_before_region_of_the_wrong_arity():
    block, _ = entry()
    one = add(block, stmts.ConstInt(value=1)).result
    before = ir.Block()  # The before block has no argument for the input.
    bit = stmts.ConstInt(value=1, bitwidth=1)
    before.stmts.append(bit)
    before.stmts.append(stmts.Yield(bit.result, one))
    after = ir.Block()
    after.args.append_from(types.Int, "out")
    after.stmts.append(stmts.Yield(after.args[0]))
    loop = add(block, stmts.While((one,), ir.Region(before), ir.Region(after)))
    with pytest.raises(ir.ValidationError, match="while before-region arity mismatch"):
        check(method(block, loop.results[0], types.Int))


def test_rejects_a_while_after_region_yielding_another_family():
    block, _ = entry()
    one = add(block, stmts.ConstInt(value=1)).result
    loop = while_loop(
        block,
        (one,),
        lambda b, n: (_bit(b), n),
        # The after region yields a bit where the loop carries an int.
        lambda b, n: (_bit(b),),
    )
    with pytest.raises(
        ir.ValidationError, match="while after-region yields bool where int"
    ):
        check(method(block, loop.results[0], types.Int))


@pytest.mark.parametrize(
    "value, bitwidth, message",
    [
        (-1, 1, "does not fit 1 bits"),
        (1.5, 32, "is not an integer"),
        (True, 32, "is not an integer"),
        (1, 0, "is not positive"),
    ],
)
def test_rejects_a_malformed_constant(value, bitwidth, message):
    block, _ = entry()
    add(block, stmts.ConstInt(value=value, bitwidth=bitwidth))
    with pytest.raises(ir.ValidationError, match=message):
        check(method(block, None, types.NoneType))


def test_rejects_a_constant_typed_against_its_bitwidth():
    block, _ = entry()
    wide = add(block, stmts.ConstInt(value=5, bitwidth=64))
    wide.result.type = types.Bool
    with pytest.raises(ir.ValidationError, match="64-bit constant is typed bool"):
        check(method(block, None, types.NoneType))


def test_rejects_a_call_to_something_that_is_not_a_method():
    block, _ = entry()
    add(block, stmts.Call(42, (), ()))  # type: ignore[arg-type]
    with pytest.raises(ir.ValidationError, match="is not a method"):
        check(method(block, None, types.NoneType))


def test_rejects_a_negative_register_size():
    block, _ = entry()
    size = add(block, stmts.ConstInt(value=-3)).result
    reg = add(block, stmts.RegAlloc(size)).result
    add(block, stmts.RegFree(reg))
    with pytest.raises(ir.ValidationError, match="a register of -3 qubits"):
        check(method(block, None, types.NoneType))


@pytest.mark.parametrize("index", [2, -1])
def test_rejects_a_constant_index_outside_the_register(index):
    block, _ = entry()
    two = add(block, stmts.ConstInt(value=2)).result
    slot = add(block, stmts.ConstInt(value=index)).result
    reg = add(block, stmts.RegAlloc(two)).result
    reg.type = qureg(2)
    taken = add(block, stmts.Extract(reg, slot))
    back = add(block, stmts.Insert(taken.result_reg, slot, taken.wire))
    add(block, stmts.RegFree(back.result))
    with pytest.raises(ir.ValidationError, match=f"slot {index} is outside"):
        check(method(block, None, types.NoneType))


def test_rejects_a_bitwise_operation_on_integers_giving_a_bit():
    block, _ = entry()
    one = add(block, stmts.ConstInt(value=1)).result
    both = add(block, stmts.IntAnd(one, one))
    both.result.type = types.Bool
    with pytest.raises(
        ir.ValidationError, match="an operation on integers must give an integer"
    ):
        check(method(block, None, types.NoneType))


def test_a_callee_declaring_any_accepts_its_calls():
    callee_block, _ = entry()
    bit = add(callee_block, stmts.ConstInt(value=1, bitwidth=1)).result
    callee = method(callee_block, (bit, bit), types.Any, name="pair")
    block, _ = entry()
    call = add(block, stmts.Call(callee, (), (types.Bool, types.Bool)))
    check(method(block, call.results[0], types.Bool))


@pytest.mark.parametrize("retype", [types.Int, types.Bool])
def test_rejects_an_integer_result_of_another_family(retype):
    block, _ = entry()
    operand = add(
        block, stmts.ConstInt(value=1, bitwidth=1 if retype is types.Int else 32)
    ).result
    total = add(block, stmts.IntAdd(operand, operand))
    total.result.type = retype
    with pytest.raises(ir.ValidationError, match="must give"):
        check(method(block, None, types.NoneType))


def test_rejects_a_select_between_a_bit_and_an_integer():
    block, _ = entry()
    bit = add(block, stmts.ConstInt(value=1, bitwidth=1)).result
    number = add(block, stmts.ConstInt(value=7)).result
    picked = add(block, stmts.IntSelect(bit, bit, number))
    with pytest.raises(ir.ValidationError, match="two bits or two integers"):
        check(method(block, picked.result, types.Int))


@pytest.mark.parametrize(
    "statement, message",
    [
        (
            lambda: stmts.IntArrayConst(values=(7, 2**40), bitwidth=1),
            "does not fit 1 bits",
        ),
        (lambda: stmts.IntArrayConst(values=(1.5,), bitwidth=32), "is not an integer"),
        (lambda: stmts.IntArrayConst(values=(1,), bitwidth=0), "is not positive"),
        (lambda: stmts.ConstFloat(value="abc"), "is not a number"),
    ],
)
def test_rejects_a_malformed_array_or_float_constant(statement, message):
    block, _ = entry()
    add(block, statement())
    with pytest.raises(ir.ValidationError, match=message):
        check(method(block, None, types.NoneType))


def test_rejects_an_array_element_of_another_family():
    block, _ = entry()
    bit = add(block, stmts.ConstInt(value=1, bitwidth=1)).result
    number = add(block, stmts.ConstInt(value=7)).result
    add(block, stmts.IntArrayCreate((bit, number), bitwidth=1))
    with pytest.raises(ir.ValidationError, match="1-bit array takes a value typed int"):
        check(method(block, None, types.NoneType))


@pytest.mark.parametrize("index, size", [(-1, 2), (5, 2)])
def test_rejects_a_slot_outside_an_allocated_register(index, size):
    block, _ = entry()
    count = add(block, stmts.ConstInt(value=size)).result
    slot = add(block, stmts.ConstInt(value=index)).result
    reg = add(block, stmts.RegAlloc(count)).result
    taken = add(block, stmts.Extract(reg, slot))
    back = add(block, stmts.Insert(taken.result_reg, slot, taken.wire))
    add(block, stmts.RegFree(back.result))
    with pytest.raises(ir.ValidationError, match=f"slot {index} is outside"):
        check(method(block, None, types.NoneType))


def test_rejects_a_register_that_changes_length_through_an_extract():
    block, _ = entry()
    count = add(block, stmts.ConstInt(value=2)).result
    zero = add(block, stmts.ConstInt(value=0)).result
    reg = add(block, stmts.RegAlloc(count)).result
    reg.type = qureg(2)
    taken = add(block, stmts.Extract(reg, zero))
    taken.result_reg.type = qureg(9)
    back = add(block, stmts.Insert(taken.result_reg, zero, taken.wire))
    add(block, stmts.RegFree(back.result))
    with pytest.raises(ir.ValidationError, match="comes out typed qureg\\[9\\]"):
        check(method(block, None, types.NoneType))


def test_rejects_a_pauli_string_that_does_not_match_the_targets():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    angle = add(block, stmts.ConstFloat(value=0.5)).result
    rotated = add(block, stmts.Ppr((w,), (), angle, pauli_string=("x", "q", "z")))
    add(block, stmts.Free(rotated.results[0]))
    with pytest.raises(ir.ValidationError, match="3 letters acts on 1 targets"):
        check(method(block, None, types.NoneType))


@pytest.mark.parametrize("operation", [stmts.IntLtS, stmts.IntEq])
def test_rejects_a_comparison_between_a_bit_and_an_integer(operation):
    block, _ = entry()
    bit = add(block, stmts.ConstInt(value=1, bitwidth=1)).result
    number = add(block, stmts.ConstInt(value=7)).result
    add(block, operation(bit, number))
    with pytest.raises(ir.ValidationError, match="mixes a bit with an integer"):
        check(method(block, None, types.NoneType))


@pytest.mark.parametrize("operation", [stmts.IntOr, stmts.IntXor])
def test_rejects_a_bitwise_operation_on_bits_giving_an_integer(operation):
    block, _ = entry()
    bit = add(block, stmts.ConstInt(value=1, bitwidth=1)).result
    result = add(block, operation(bit, bit))
    result.result.type = types.Int
    with pytest.raises(
        ir.ValidationError, match="an operation on bits must give a bit"
    ):
        check(method(block, None, types.NoneType))


def test_rejects_a_constant_too_wide_for_its_bitwidth():
    block, _ = entry()
    add(block, stmts.ConstInt(value=128, bitwidth=8))
    with pytest.raises(ir.ValidationError, match="constant 128 does not fit 8 bits"):
        check(method(block, None, types.NoneType))


def test_rejects_a_float_constant_of_another_bitwidth():
    block, _ = entry()
    add(block, stmts.ConstFloat(value=0.5, bitwidth=32))
    with pytest.raises(
        ir.ValidationError, match="has bitwidth 64, and this one has 32"
    ):
        check(method(block, None, types.NoneType))


def test_rejects_an_array_element_typed_against_its_bitwidth():
    block, _ = entry()
    zeros = add(block, stmts.IntArrayConst(values=(0, 0), bitwidth=32)).result
    zero = add(block, stmts.ConstInt(value=0)).result
    got = add(block, stmts.IntArrayGet(zeros, zero, bitwidth=32))
    got.result.type = types.Bool
    with pytest.raises(ir.ValidationError, match="32-bit element is typed bool"):
        check(method(block, None, types.NoneType))


def test_rejects_a_letter_that_is_no_pauli_letter():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    angle = add(block, stmts.ConstFloat(value=0.5)).result
    rotated = add(block, stmts.Ppr((w,), (), angle, pauli_string=("q",)))
    add(block, stmts.Free(rotated.results[0]))
    with pytest.raises(ir.ValidationError, match="'q' is no Pauli letter"):
        check(method(block, None, types.NoneType))


def test_rejects_an_insert_outside_a_created_register():
    """The register length comes from the wires that created the register.

    The length survives the extract that comes before the insert.
    """
    block, _ = entry()
    a = add(block, stmts.Alloc()).result
    b = add(block, stmts.Alloc()).result
    reg = add(block, stmts.RegCreate((a, b))).result
    zero = add(block, stmts.ConstInt(value=0)).result
    five = add(block, stmts.ConstInt(value=5)).result
    taken = add(block, stmts.Extract(reg, zero))
    back = add(block, stmts.Insert(taken.result_reg, five, taken.wire))
    add(block, stmts.RegFree(back.result))
    with pytest.raises(
        ir.ValidationError, match="slot 5 is outside a register of 2 qubits"
    ):
        check(method(block, None, types.NoneType))


def test_a_return_under_an_any_output_is_unchecked():
    block, _ = entry()
    bit = add(block, stmts.ConstInt(value=1, bitwidth=1)).result
    check(method(block, (bit, bit, bit), types.Any))


def test_rejects_a_returned_value_of_type_bottom():
    block, _ = entry()
    value = add(block, stmts.ConstInt(value=1)).result
    value.type = types.Bottom
    with pytest.raises(ir.TypeCheckError, match="the return gives"):
        check(method(block, value, types.Int))
