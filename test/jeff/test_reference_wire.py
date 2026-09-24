"""Test the reference analysis on jeff wires, registers, loops, switches and calls."""

from kirin import types

from bloqade import jeff
from bloqade.jeff.types import qureg
from bloqade.jeff.dialects import stmts
from bloqade.analysis.reference import (
    UNTRACKED,
    Slot,
    Bottom,
    Whole,
    Unknown,
    Register,
    Returned,
    Positions,
)
from bloqade.jeff.analysis.wire import WireReferenceAnalysis

from .build import add, entry, method, switch, for_loop, while_loop


def returned(mt):
    """Return the references of the values that `mt` returns."""
    _, result = WireReferenceAnalysis(jeff.kernel).run(mt)
    assert isinstance(result, Positions)
    return result.refs


def reason(ref) -> str | None:
    return ref.reason if isinstance(ref, Unknown) else None


def constants(block, *values):
    return [add(block, stmts.ConstInt(value=v)).result for v in values]


def gate(block, name, *wires):
    return add(block, stmts.Gate(tuple(wires), (), (), gate_name=name)).results


def test_a_gate_a_measurement_and_a_loop_hand_their_wires_on():
    block, (q0, q1) = entry(jeff.WireType, jeff.WireType)
    (gated,) = gate(block, "h", q0)
    measured = add(block, stmts.MeasureNd(gated))
    lo, hi, one = constants(block, 0, 2, 1)
    loop = for_loop(block, lo, hi, one, (q1,), lambda b, i, s: gate(b, "x", s))
    mt = method(
        block,
        (measured.bit, measured.result_wire, loop.results[0]),
        types.Generic(tuple, types.Bool, jeff.WireType, jeff.WireType),
        inputs=(jeff.WireType, jeff.WireType),
    )
    assert returned(mt) == (UNTRACKED, Whole(q0), Whole(q1))


def test_a_loop_that_swaps_its_wires_loses_both():
    block, (q0, q1) = entry(jeff.WireType, jeff.WireType)
    lo, hi, one = constants(block, 0, 2, 1)
    loop = for_loop(block, lo, hi, one, (q0, q1), lambda b, i, a, c: (c, a))
    mt = method(
        block,
        tuple(loop.results),
        types.Generic(tuple, jeff.WireType, jeff.WireType),
        inputs=(jeff.WireType, jeff.WireType),
    )
    assert [reason(ref) for ref in returned(mt)] == [
        "a value carried by a loop or branch"
    ] * 2


def flip_second_if():
    """Build a function that measures its first wire and may flip its second."""
    block, (w0, w1, c) = entry(jeff.WireType, jeff.WireType, types.Int)
    picked = switch(block, c, (w1,), [lambda b, s: (s,)], lambda b, s: gate(b, "x", s))
    bit = add(block, stmts.Measure(w0)).bit
    return method(
        block,
        (bit, picked.results[0]),
        types.Generic(tuple, types.Bool, jeff.WireType),
        inputs=(jeff.WireType, jeff.WireType, types.Int),
        name="flip_second_if",
    )


def test_a_switch_hands_on_a_wire_that_every_branch_yields():
    callee = flip_second_if()
    w1 = callee.callable_region.blocks[0].args[2]
    assert returned(callee) == (UNTRACKED, Whole(w1))


def test_a_call_hands_back_the_wire_of_the_caller():
    callee = flip_second_if()
    block, (a, b) = entry(jeff.WireType, jeff.WireType)
    (c,) = constants(block, 0)
    call = add(block, stmts.Call(callee, (a, b, c), (types.Bool, jeff.WireType)))
    mt = method(
        block,
        (call.results[1],),
        jeff.WireType,
        inputs=(jeff.WireType, jeff.WireType),
    )
    assert returned(mt) == (Whole(b),)


def test_a_wire_that_a_callee_allocates_is_rooted_at_the_call():
    inner, _ = entry()
    fresh = add(inner, stmts.Alloc()).result
    callee = method(inner, (fresh,), jeff.WireType, name="make")
    block, _ = entry()
    call = add(block, stmts.Call(callee, (), (jeff.WireType,)))
    mt = method(block, (call.results[0],), jeff.WireType)
    (ref,) = returned(mt)
    assert ref == Whole(Returned(call, 0, fresh))
    assert repr(ref) == "Whole(make()[0])"


def test_a_wire_inserted_into_its_own_slot_hands_the_register_on():
    block, (reg,) = entry(qureg(2))
    zero, one = constants(block, 0, 1)
    extracted = add(block, stmts.Extract(reg, zero))
    (flipped,) = gate(block, "x", extracted.wire)
    back = add(block, stmts.Insert(extracted.result_reg, zero, flipped))
    moved = add(block, stmts.Extract(back.result, zero))
    elsewhere = add(block, stmts.Insert(moved.result_reg, one, moved.wire))
    mt = method(
        block,
        (back.result, elsewhere.result),
        types.Generic(tuple, jeff.QuregType, jeff.QuregType),
        inputs=(qureg(2),),
    )
    frame, _ = WireReferenceAnalysis(jeff.kernel).run(mt)
    assert frame.entries[extracted.wire] == Slot(reg, 0)
    assert frame.entries[back.result] == Register(reg)
    assert reason(frame.entries[elsewhere.result]) == (
        "a register that holds a wire from another slot"
    )


def test_a_call_that_only_returns_itself_has_no_reference():
    block, (q,) = entry(jeff.WireType)
    mt = method(block, (q,), jeff.WireType, inputs=(jeff.WireType,), name="rec")
    ret = block.last_stmt
    call = stmts.Call(mt, (q,), (jeff.WireType,))
    call.insert_before(ret)
    ret.replace_by(stmts.Return(call.results[0]))
    (ref,) = returned(mt)
    assert ref == Bottom()


def test_a_recursion_with_a_base_case_hands_its_wire_back():
    """`rec(n, w)` flips `w` and calls itself with `n - 1` until `n` is 0."""
    block, (n, w) = entry(types.Int, jeff.WireType)
    (zero,) = constants(block, 0)
    done = add(block, stmts.IntLteS(n, zero)).result
    mt = method(
        block,
        (w, n),
        types.Generic(tuple, jeff.WireType, types.Int),
        inputs=(types.Int, jeff.WireType),
        name="rec",
    )

    def base(body, n_, w_):
        return [w_, n_]

    def step(body, n_, w_):
        (one,) = constants(body, 1)
        less = add(body, stmts.IntSub(n_, one)).result
        (flipped,) = gate(body, "x", w_)
        call = add(body, stmts.Call(mt, (less, flipped), (jeff.WireType, types.Int)))
        return [call.results[0], call.results[1]]

    ret = block.last_stmt
    chosen = switch(block, done, (n, w), [step], base)
    chosen.detach()
    chosen.insert_before(ret)
    ret.replace_by(stmts.Return(chosen.results[0], chosen.results[1]))
    assert returned(mt) == (Whole(w), UNTRACKED)


def test_a_mutually_recursive_call_that_only_returns_itself_has_no_reference():
    """`ping` calls `pong`, which calls `ping` again."""
    pong_block, (p,) = entry(jeff.WireType)
    pong = method(pong_block, (p,), jeff.WireType, inputs=(jeff.WireType,), name="pong")
    ping_block, (q,) = entry(jeff.WireType)
    call_pong = add(ping_block, stmts.Call(pong, (q,), (jeff.WireType,)))
    ping = method(
        ping_block,
        (call_pong.results[0],),
        jeff.WireType,
        inputs=(jeff.WireType,),
        name="ping",
    )
    ret = pong_block.last_stmt
    call_ping = stmts.Call(ping, (p,), (jeff.WireType,))
    call_ping.insert_before(ret)
    ret.replace_by(stmts.Return(call_ping.results[0]))
    (ref,) = returned(ping)
    assert ref == Bottom()


def test_a_returned_register_keeps_its_allocated_length():
    inner, _ = entry()
    (three,) = constants(inner, 3)
    made = add(inner, stmts.RegAlloc(three)).result
    measured = add(inner, stmts.RegLength(made))
    callee = method(inner, (measured.result_reg,), jeff.QuregType, name="make")
    block, (q,) = entry(jeff.WireType)
    reset = add(block, stmts.Reset(q)).result
    call = add(block, stmts.Call(callee, (), (jeff.QuregType,)))
    (last,) = constants(block, -1)
    extracted = add(block, stmts.Extract(call.results[0], last))
    mt = method(
        block,
        (reset, extracted.result_reg, extracted.wire),
        types.Generic(tuple, jeff.WireType, jeff.QuregType, jeff.WireType),
        inputs=(jeff.WireType,),
    )
    root = Returned(call, 0, made)
    assert returned(mt) == (Whole(q), Register(root), Slot(root, 2))


def test_a_callee_runs_with_the_references_of_the_caller():
    callee = flip_second_if()
    block, (a, b) = entry(jeff.WireType, jeff.WireType)
    (c,) = constants(block, 0)
    call = add(block, stmts.Call(callee, (a, b, c), (types.Bool, jeff.WireType)))
    mt = method(
        block,
        (call.results[1],),
        jeff.WireType,
        inputs=(jeff.WireType, jeff.WireType),
    )
    frame, _ = WireReferenceAnalysis(jeff.kernel).run(mt)
    assert frame.entries[call.results[1]] == Whole(b)


def test_a_while_loop_hands_on_the_wire_that_it_carries():
    block, (q,) = entry(jeff.WireType)

    def before(b, w):
        measured = add(b, stmts.MeasureNd(w))
        return (measured.bit, measured.result_wire)

    loop = while_loop(block, (q,), before, lambda b, w: gate(b, "x", w))
    mt = method(block, tuple(loop.results), jeff.WireType, inputs=(jeff.WireType,))
    frame, result = WireReferenceAnalysis(jeff.kernel).run(mt)
    assert result == Positions((Whole(q),))
    inner = loop.after.blocks[0].args[0]
    assert frame.entries[inner] == Whole(q)


def test_a_while_loop_that_swaps_its_wires_loses_both():
    block, (q0, q1) = entry(jeff.WireType, jeff.WireType)

    def before(b, a, c):
        measured = add(b, stmts.MeasureNd(a))
        return (measured.bit, c, measured.result_wire)

    loop = while_loop(block, (q0, q1), before, lambda b, a, c: (a, c))
    mt = method(
        block,
        tuple(loop.results),
        types.Generic(tuple, jeff.WireType, jeff.WireType),
        inputs=(jeff.WireType, jeff.WireType),
    )
    assert [reason(ref) for ref in returned(mt)] == [
        "a value carried by a loop or branch"
    ] * 2
