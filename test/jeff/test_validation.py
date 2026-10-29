"""Test the validation passes that check rules spanning several statements.

The passes check block terminators, operand scope, region isolation, jeff-only
statements, and the linear use of wires and registers.
"""

import pytest
from kirin import ir, types
from kirin.dialects import py, scf, func
from kirin.ir.exception import ValidationErrorGroup

from bloqade import jeff
from bloqade.squin.gate import stmts as gate_stmts
from bloqade.jeff.dialects import stmts

from .build import add, entry, method, switch, for_loop, validate, while_loop


def _bit(block):
    return add(block, stmts.ConstInt(value=1, bitwidth=1)).result


def test_accepts_linear_program():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    w = add(block, stmts.Gate((w,), (), (), gate_name="h")).results[0]
    m = add(block, stmts.MeasureNd(w))
    add(block, stmts.Free(m.result_wire))
    validate(method(block, m.bit, types.Bool))


def test_rejects_wire_used_twice():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    add(block, stmts.Gate((w,), (), (), gate_name="h"))
    # This gate uses `w` a second time.
    add(block, stmts.Gate((w,), (), (), gate_name="h"))
    with pytest.raises(ValidationErrorGroup, match="exactly once"):
        validate(method(block, None, types.NoneType))


def test_rejects_unconsumed_wire():
    block, _ = entry()
    add(block, stmts.Alloc())  # No statement frees this wire.
    with pytest.raises(ValidationErrorGroup, match="exactly once"):
        validate(method(block, None, types.NoneType))


def test_rejects_parameter_used_twice():
    block, (w,) = entry(jeff.WireType)
    pair = types.Generic(tuple, jeff.WireType, jeff.WireType)
    with pytest.raises(ValidationErrorGroup, match="parameter .* has 2 uses"):
        validate(method(block, (w, w), pair, inputs=(jeff.WireType,)))


def test_rejects_unconsumed_parameter():
    block, _ = entry(jeff.WireType)
    with pytest.raises(ValidationErrorGroup, match="parameter .* has 0 uses"):
        validate(method(block, None, types.NoneType, inputs=(jeff.WireType,)))


def test_rejects_non_isolated_region():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    outside = add(block, stmts.ConstFloat(value=0.5)).result
    lo = add(block, stmts.ConstInt(value=0)).result
    hi = add(block, stmts.ConstInt(value=2)).result
    one = add(block, stmts.ConstInt(value=1)).result
    for_loop(
        block,
        lo,
        hi,
        one,
        (w,),
        # The body reads `outside`, which the enclosing block defines.
        lambda b, i, s: (
            add(b, stmts.Gate((s,), (), (outside,), gate_name="rz")).results[0],
        ),
    )
    with pytest.raises(ValidationErrorGroup, match="isolated"):
        validate(method(block, None, types.NoneType))


def test_rejects_python_plumbing():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    m = add(block, stmts.MeasureNd(w))
    add(block, stmts.Free(m.result_wire))
    pair = add(block, py.tuple.New((m.bit, m.bit)))
    with pytest.raises(ValidationErrorGroup, match="'new' of dialect 'py.tuple'"):
        validate(method(block, pair.result, types.Any))


def test_rejects_kirin_return():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    m = add(block, stmts.MeasureNd(w))
    add(block, stmts.Free(m.result_wire))
    block.stmts.append(func.Return(m.bit))
    code = func.Function(
        sym_name="k",
        body=ir.Region(block),
        signature=func.Signature(inputs=(), output=types.Bool),
    )
    with pytest.raises(ValidationErrorGroup, match="jeff return"):
        validate(ir.Method(dialects=jeff.kernel, code=code, sym_name="k"))


def test_accepts_multiple_outputs():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    m = add(block, stmts.MeasureNd(w))
    add(block, stmts.Free(m.result_wire))
    validate(method(block, (m.bit, m.bit), types.Any))


def test_rejects_foreign_dialect():
    block, _ = entry()
    a = add(block, stmts.ConstInt(value=1)).result
    b = add(block, stmts.ConstInt(value=2)).result
    add(block, py.binop.Add(a, b))  # This py statement is foreign to jeff.
    with pytest.raises(ValidationErrorGroup, match="not a jeff"):
        validate(method(block, None, types.NoneType))


def test_validates_callees_too():
    callee_block, _ = entry()
    w = add(callee_block, stmts.Alloc()).result
    add(callee_block, stmts.Gate((w,), (), (), gate_name="h"))
    add(callee_block, stmts.Gate((w,), (), (), gate_name="h"))
    callee = method(callee_block, None, types.NoneType)
    block, _ = entry()
    add(block, stmts.Call(callee, (), ()))
    with pytest.raises(ValidationErrorGroup, match="exactly once"):
        validate(method(block, None, types.NoneType))


def test_rejects_a_value_escaping_its_region():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    lo = add(block, stmts.ConstInt(value=0)).result
    hi = add(block, stmts.ConstInt(value=2)).result
    one = add(block, stmts.ConstInt(value=1)).result
    inside: list = []

    def body(b, i, s):
        gated = add(b, stmts.Gate((s,), (), (), gate_name="h")).results[0]
        inside.append(gated)
        return (gated,)

    loop = for_loop(block, lo, hi, one, (w,), body)
    # The enclosing block frees a wire that the loop body defines.
    add(block, stmts.Free(inside[0]))
    add(block, stmts.Free(loop.results[0]))
    with pytest.raises(ValidationErrorGroup, match="reads a value from inside"):
        validate(method(block, None, types.NoneType))


def test_rejects_a_branch_reading_a_sibling_branch():
    block, _ = entry()
    made: list = []
    selector = add(block, stmts.ConstInt(value=0)).result

    def first(b):
        made.append(add(b, stmts.Alloc()).result)
        return ()

    def second(b):
        add(b, stmts.Free(made[0]))
        return ()

    switch(block, selector, (), [first, second], lambda b: ())
    with pytest.raises(ValidationErrorGroup, match="isolated"):
        validate(method(block, None, types.NoneType))


def test_rejects_an_operand_out_of_scope():
    block, _ = entry()
    const = add(block, stmts.ConstInt(value=1))
    negated = add(block, stmts.IntNot(const.result)).result
    const.detach()  # The result of the detached constant stays in use.
    with pytest.raises(
        ValidationErrorGroup, match="has no definition that reaches this statement"
    ):
        validate(method(block, negated, types.Int))


def test_rejects_a_function_body_that_does_not_end_in_a_return():
    block, _ = entry()
    mt = method(block, None, types.NoneType)
    block.stmts.append(stmts.ConstInt(value=1))
    with pytest.raises(ValidationErrorGroup, match="must end in a jeff return"):
        validate(mt)


def test_rejects_statements_after_a_terminator():
    block, _ = entry()
    add(block, stmts.Return())
    with pytest.raises(ValidationErrorGroup, match="after its terminator"):
        validate(method(block, None, types.NoneType))


def test_rejects_a_squin_statement():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    add(block, gate_stmts.H(w))
    add(block, stmts.Free(w))
    with pytest.raises(ValidationErrorGroup, match="not a jeff statement"):
        validate(method(block, None, types.NoneType))


def test_rejects_a_kirin_scf_statement():
    block, _ = entry()
    add(block, scf.Yield())
    with pytest.raises(ValidationErrorGroup, match="not a jeff statement"):
        validate(method(block, None, types.NoneType))


def test_accepts_extracts_and_inserts_on_a_register():
    block, _ = entry()
    two = add(block, stmts.ConstInt(value=2)).result
    zero = add(block, stmts.ConstInt(value=0)).result
    one = add(block, stmts.ConstInt(value=1)).result
    reg = add(block, stmts.RegAlloc(two)).result
    first = add(block, stmts.Extract(reg, zero))
    second = add(block, stmts.Extract(first.result_reg, one))
    back = add(block, stmts.Insert(second.result_reg, one, second.wire))
    whole = add(block, stmts.Insert(back.result, zero, first.wire))
    add(block, stmts.RegFree(whole.result))
    validate(method(block, None, types.NoneType))


def test_rejects_an_operand_from_nowhere():
    block, _ = entry()
    add(block, stmts.Free(ir.TestValue(jeff.WireType)))
    with pytest.raises(
        ValidationErrorGroup, match="has no definition that reaches this statement"
    ):
        validate(method(block, None, types.NoneType))


def test_rejects_a_nested_while_reading_outside_its_loop():
    """A while loop inside a loop body takes its inputs from that body."""
    block, _ = entry()
    lo = add(block, stmts.ConstInt(value=0)).result
    hi = add(block, stmts.ConstInt(value=1)).result
    one = add(block, stmts.ConstInt(value=1)).result
    outside = add(block, stmts.ConstInt(value=7)).result

    def body(b, i, n):
        loop = while_loop(
            b, (outside,), lambda inner, m: (_bit(inner), m), lambda inner, m: (m,)
        )
        return (loop.results[0],)

    loop = for_loop(block, lo, hi, one, (one,), body)
    with pytest.raises(ValidationErrorGroup, match="isolated"):
        validate(method(block, loop.results[0], types.Int))


def test_a_malformed_nested_statement_is_reported_once():
    """The check of an inner loop reports that loop's defect once.

    The validation stops before it reads the types of the broken loop.
    """
    block, _ = entry()
    zero = add(block, stmts.ConstInt(value=0)).result
    inner = ir.Block()
    inner.args.append_from(types.Int, "j")
    inner.stmts.append(stmts.Yield())
    outer = ir.Block()
    outer.args.append_from(types.Int, "i")
    lo = stmts.ConstInt(value=0)
    outer.stmts.append(lo)
    outer.stmts.append(stmts.For(lo.result, lo.result, lo.result, (), ir.Region([])))
    outer.stmts.append(stmts.Yield())
    add(block, stmts.For(zero, zero, zero, (), ir.Region(outer)))
    with pytest.raises(ValidationErrorGroup) as info:
        validate(method(block, None, types.NoneType))
    messages = [error.args[0] for error in info.value.errors]
    assert messages == ["a region of 'for' must hold one block"]


def test_a_use_by_a_detached_statement_does_not_count():
    """A detached statement keeps its uses on the value.

    Only uses by statements inside the function count.
    """
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    gate = add(block, stmts.Gate((w,), (), (), gate_name="h"))
    freed = add(block, stmts.Free(gate.results[0]))
    freed.detach()
    gate.detach()
    add(block, stmts.Free(w))
    validate(method(block, None, types.NoneType))


def test_rejects_a_wire_left_unconsumed_beside_a_detached_use():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    stmts.Free(w)  # This `Free` statement stays outside every block.
    with pytest.raises(ValidationErrorGroup, match="has 0 uses"):
        validate(method(block, None, types.NoneType))


def test_rejects_a_function_body_of_two_blocks():
    block, _ = entry()
    mt = method(block, None, types.NoneType)
    second = ir.Block()
    second.stmts.append(stmts.Return())
    mt.callable_region.blocks.append(second)
    with pytest.raises(ValidationErrorGroup, match="must hold one block"):
        validate(mt)


def test_reports_statement_defects_in_every_function():
    callee_block, _ = entry()
    add(callee_block, stmts.ConstInt(value=99, bitwidth=2))
    callee = method(callee_block, None, types.NoneType, name="callee")
    block, _ = entry()
    add(block, stmts.ConstInt(value=99, bitwidth=3))
    add(block, stmts.Call(callee, (), ()))
    with pytest.raises(ValidationErrorGroup) as info:
        validate(method(block, None, types.NoneType))
    messages = sorted(error.args[0] for error in info.value.errors)
    assert messages == [
        "constant 99 does not fit 2 bits",
        "constant 99 does not fit 3 bits",
    ]


def test_rejects_a_function_body_without_blocks():
    block, _ = entry()
    mt = method(block, None, types.NoneType)
    mt.callable_region.blocks[0].delete(safe=False)
    with pytest.raises(ValidationErrorGroup, match="must hold one block"):
        validate(mt)


def test_reports_a_defect_in_a_recursive_function_once():
    block, _ = entry()
    add(block, stmts.ConstInt(value=99, bitwidth=2))
    mt = method(block, None, types.NoneType, name="recursive")
    # The call enters `mt` while the analysis runs `mt`.
    ret = block.last_stmt
    assert ret is not None
    stmts.Call(mt, (), ()).insert_before(ret)
    with pytest.raises(ValidationErrorGroup) as info:
        validate(mt)
    assert [error.args[0] for error in info.value.errors] == [
        "constant 99 does not fit 2 bits"
    ]


def _messages(mt: ir.Method) -> list[str]:
    with pytest.raises(ValidationErrorGroup) as info:
        validate(mt)
    return sorted(error.args[0] for error in info.value.errors)


def test_checks_the_statements_after_a_foreign_statement():
    block, _ = entry()
    a = add(block, stmts.ConstInt(value=1)).result
    add(block, py.binop.Add(a, a))
    add(block, py.binop.Sub(a, a))
    add(block, stmts.Alloc())  # No statement frees this wire.
    messages = _messages(method(block, None, types.NoneType))
    assert "statement 'add' of dialect 'py.binop' is not a jeff statement" in messages
    assert "statement 'sub' of dialect 'py.binop' is not a jeff statement" in messages
    assert any("exactly once" in message for message in messages)


def test_checks_the_caller_after_a_callee_with_a_foreign_statement():
    callee_block, _ = entry()
    a = add(callee_block, stmts.ConstInt(value=1)).result
    add(callee_block, py.binop.Add(a, a))
    callee = method(callee_block, None, types.NoneType, name="callee")
    block, _ = entry()
    add(block, stmts.Call(callee, (), ()))
    add(block, stmts.Alloc())  # No statement frees this wire.
    messages = _messages(method(block, None, types.NoneType))
    assert "statement 'add' of dialect 'py.binop' is not a jeff statement" in messages
    assert any("exactly once" in message for message in messages)


def test_rejects_a_callee_without_blocks():
    callee_block, _ = entry()
    callee = method(callee_block, None, types.NoneType, name="callee")
    callee.callable_region.blocks[0].delete(safe=False)
    block, _ = entry()
    add(block, stmts.Call(callee, (), ()))
    assert "a jeff function body must hold one block" in _messages(
        method(block, None, types.NoneType)
    )


def test_rejects_statements_after_a_yield():
    block, _ = entry()
    zero = add(block, stmts.ConstInt(value=0)).result

    def body(inner, i):
        inner.stmts.append(stmts.Yield())  # The builder appends a second yield.
        return ()

    for_loop(block, zero, zero, zero, (), body)
    with pytest.raises(ValidationErrorGroup, match="after its terminator"):
        validate(method(block, None, types.NoneType))


def test_accepts_a_wire_carried_through_every_control_flow_statement():
    block, _ = entry()
    zero = add(block, stmts.ConstInt(value=0)).result
    w = add(block, stmts.Alloc()).result
    w = for_loop(block, zero, zero, zero, (w,), lambda b, i, v: (v,)).results[0]
    w = switch(block, zero, (w,), [lambda b, v: (v,)], lambda b, v: (v,)).results[0]
    loop = while_loop(block, (w,), lambda b, v: (_bit(b), v), lambda b, v: (v,))
    add(block, stmts.Free(loop.results[0]))
    validate(method(block, None, types.NoneType))


def test_checks_a_method_of_another_dialect_group():
    block, _ = entry()
    zero = add(block, stmts.ConstInt(value=0)).result

    def body(b, i):
        add(b, py.binop.Add(i, i))
        return ()

    for_loop(block, zero, zero, zero, (), body)
    mt = method(block, None, types.NoneType)
    mt.dialects = jeff.dialects.function  # This group has no jeff.scf dialect.
    assert "statement 'add' of dialect 'py.binop' is not a jeff statement" in (
        _messages(mt)
    )


def test_rejects_a_function_body_that_ends_in_a_yield():
    block, _ = entry()
    value = add(block, stmts.ConstInt(value=1)).result
    mt = method(block, None, types.NoneType)
    ret = block.last_stmt
    assert ret is not None
    ret.replace_by(stmts.Yield(value))
    assert _messages(mt) == ["a jeff function body must end in a jeff return"]


def test_reports_a_use_before_the_definition_inside_a_region():
    block, _ = entry()
    zero = add(block, stmts.ConstInt(value=0)).result

    def body(b, i):
        later = stmts.ConstInt(value=1)
        add(b, stmts.IntNot(later.result))
        add(b, later)
        return ()

    for_loop(block, zero, zero, zero, (), body)
    messages = _messages(method(block, None, types.NoneType))
    assert len(messages) == 1
    assert "has no definition that reaches this statement" in messages[0]


def test_checks_a_callee_after_a_call_of_the_wrong_arity():
    callee_block, _ = entry()
    one = add(callee_block, stmts.ConstInt(value=1)).result
    add(callee_block, py.binop.Add(one, one))
    callee = method(callee_block, None, types.NoneType, name="callee")
    block, _ = entry()
    extra = add(block, stmts.ConstInt(value=1)).result
    add(block, stmts.Call(callee, (extra,), ()))
    add(block, stmts.Call(callee, (), ()))
    assert "statement 'add' of dialect 'py.binop' is not a jeff statement" in (
        _messages(method(block, None, types.NoneType))
    )


def test_reports_a_region_argument_at_its_statement():
    block, _ = entry()
    zero = add(block, stmts.ConstInt(value=0)).result
    w = add(block, stmts.Alloc()).result
    extra = add(block, stmts.Alloc()).result
    loop = for_loop(block, zero, zero, zero, (w,), lambda b, i, v: (extra,))
    add(block, stmts.Free(loop.results[0]))
    with pytest.raises(ValidationErrorGroup) as info:
        validate(method(block, None, types.NoneType))
    nodes = [
        error.node for error in info.value.errors if "region argument" in str(error)
    ]
    assert nodes == [loop]


def test_rejects_a_function_reading_a_value_of_another_function():
    other_block, _ = entry()
    w = add(other_block, stmts.Alloc()).result
    add(other_block, stmts.Free(w))
    method(other_block, None, types.NoneType, name="other")
    block, _ = entry()
    h = add(block, stmts.Gate((w,), (), (), gate_name="h")).results[0]
    add(block, stmts.Free(h))
    assert _messages(method(block, None, types.NoneType)) == [
        "a block of 'func' reads a value from outside the block. "
        "Each jeff function and region must be isolated."
    ]
