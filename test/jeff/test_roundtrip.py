"""Building jeff programs as dialect IR, emitting them, importing them back,
and re-emitting reproduces the module."""

import pytest
from kirin import ir, types

from bloqade import jeff
from bloqade.jeff.dialects import stmts

from .build import add, entry, method, switch, for_loop, validate, while_loop
from .helpers import roundtrips


def gate(block, name, target, *controls, params=()):
    """A single-target gate; returns the target's output wire."""
    g = add(block, stmts.Gate((target,), controls, tuple(params), gate_name=name))
    return g.results[0]


def bell() -> ir.Method:
    block, _ = entry()
    w0 = add(block, stmts.Alloc()).result
    w1 = add(block, stmts.Alloc()).result
    w0 = gate(block, "h", w0)
    g = add(block, stmts.Gate((w1,), (w0,), (), gate_name="x"))
    w1, w0 = g.results
    m0 = add(block, stmts.MeasureNd(w0))
    m1 = add(block, stmts.MeasureNd(w1))
    bits = add(block, stmts.IntArrayCreate((m0.bit, m1.bit), bitwidth=1))
    add(block, stmts.Free(m0.result_wire))
    add(block, stmts.Free(m1.result_wire))
    return method(block, bits.result, jeff.IntArrayType, name="bell")


def rotation() -> ir.Method:
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    angle = add(block, stmts.ConstFloat(value=0.25)).result
    w = add(block, stmts.Gate((w,), (), (angle,), gate_name="rz")).results[0]
    m = add(block, stmts.MeasureNd(w))
    add(block, stmts.Free(m.result_wire))
    return method(block, m.bit, types.Bool, name="rotation")


def counted_loop() -> ir.Method:
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    lo = add(block, stmts.ConstInt(value=0)).result
    hi = add(block, stmts.ConstInt(value=3)).result
    one = add(block, stmts.ConstInt(value=1)).result
    loop = for_loop(block, lo, hi, one, (w,), lambda b, i, s: (gate(b, "h", s),))
    m = add(block, stmts.MeasureNd(loop.results[0]))
    add(block, stmts.Free(m.result_wire))
    return method(block, m.bit, types.Bool, name="counted_loop")


def nested_loop() -> ir.Method:
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    lo = add(block, stmts.ConstInt(value=0)).result
    hi = add(block, stmts.ConstInt(value=2)).result
    one = add(block, stmts.ConstInt(value=1)).result

    def inner(b, i, s):
        # a region must be isolated, so the inner loop's bounds live in it
        lo2 = add(b, stmts.ConstInt(value=0)).result
        hi2 = add(b, stmts.ConstInt(value=2)).result
        one2 = add(b, stmts.ConstInt(value=1)).result
        body = for_loop(b, lo2, hi2, one2, (s,), lambda bb, j, ss: (gate(bb, "h", ss),))
        return (body.results[0],)

    loop = for_loop(block, lo, hi, one, (w,), inner)
    m = add(block, stmts.MeasureNd(loop.results[0]))
    add(block, stmts.Free(m.result_wire))
    return method(block, m.bit, types.Bool, name="nested_loop")


def feedforward() -> ir.Method:
    block, _ = entry()
    w0 = add(block, stmts.Alloc()).result
    w1 = add(block, stmts.Alloc()).result
    m0 = add(block, stmts.MeasureNd(gate(block, "h", w0)))
    m1 = add(block, stmts.MeasureNd(w1))
    sw = switch(
        block,
        m0.bit,
        (m1.result_wire,),
        cases=[lambda b, w: (w,)],  # selector 0: leave it
        default=lambda b, w: (gate(b, "x", w),),  # else: flip it
    )
    bits = add(block, stmts.IntArrayCreate((m0.bit, m1.bit), bitwidth=1))
    add(block, stmts.Free(m0.result_wire))
    add(block, stmts.Free(sw.results[0]))
    return method(block, bits.result, jeff.IntArrayType, name="feedforward")


def rus() -> ir.Method:
    """Repeat-until-success: a while loop carrying a wire and its last bit."""
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    m = add(block, stmts.MeasureNd(w))

    def before(b, wire, bit):
        return (bit, wire, bit)  # condition, then loop outputs

    def after(b, wire, bit):
        nm = add(b, stmts.MeasureNd(gate(b, "h", wire)))
        return (nm.result_wire, nm.bit)

    loop = while_loop(block, (m.result_wire, m.bit), before, after)
    add(block, stmts.Free(loop.results[0]))
    return method(block, loop.results[1], types.Bool, name="rus")


def float_sweep() -> ir.Method:
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    angles = add(block, stmts.FloatArrayConst(values=(0.25, 0.5, 0.75))).result
    idx = add(block, stmts.ConstInt(value=1)).result
    angle = add(block, stmts.FloatArrayGet(angles, idx)).result
    w = add(block, stmts.Gate((w,), (), (angle,), gate_name="rz")).results[0]
    m = add(block, stmts.MeasureNd(w))
    add(block, stmts.Free(m.result_wire))
    return method(block, m.bit, types.Bool, name="float_sweep")


def register() -> ir.Method:
    block, _ = entry()
    n = add(block, stmts.ConstInt(value=2)).result
    reg = add(block, stmts.RegAlloc(n)).result
    idx = add(block, stmts.ConstInt(value=0)).result
    ext = add(block, stmts.Extract(reg, idx))
    w = gate(block, "h", ext.wire)
    reg = add(block, stmts.Insert(ext.result_reg, idx, w)).result
    add(block, stmts.RegFree(reg))
    return method(block, None, types.NoneType, name="register")


def register_surgery() -> ir.Method:
    block, _ = entry()
    n = add(block, stmts.ConstInt(value=4)).result
    reg = add(block, stmts.RegAlloc(n)).result
    at = add(block, stmts.ConstInt(value=2)).result
    split = add(block, stmts.RegSplit(reg, at))
    joined = add(block, stmts.RegJoin(split.before, split.after)).result
    add(block, stmts.RegFree(joined))
    return method(block, None, types.NoneType, name="register_surgery")


def with_call() -> ir.Method:
    inner_block, [w_in] = entry(jeff.WireType)
    flipped = gate(inner_block, "x", w_in)
    callee = method(
        inner_block, flipped, jeff.WireType, inputs=(jeff.WireType,), name="flip"
    )

    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    call = add(block, stmts.Call(callee, (w,), (jeff.WireType,)))
    m = add(block, stmts.MeasureNd(call.results[0]))
    add(block, stmts.Free(m.result_wire))
    return method(block, m.bit, types.Bool, name="with_call")


def two_outputs() -> ir.Method:
    """A function with two outputs: the return carries a tuple of values."""
    block, _ = entry()
    w0 = add(block, stmts.Alloc()).result
    w1 = add(block, stmts.Alloc()).result
    m0 = add(block, stmts.MeasureNd(gate(block, "x", w0)))
    m1 = add(block, stmts.MeasureNd(w1))
    add(block, stmts.Free(m0.result_wire))
    add(block, stmts.Free(m1.result_wire))
    return method(block, (m0.bit, m1.bit), types.Any, name="two_outputs")


KERNELS = [
    bell,
    rotation,
    counted_loop,
    nested_loop,
    feedforward,
    rus,
    float_sweep,
    register,
    register_surgery,
    with_call,
    two_outputs,
]


@pytest.mark.parametrize("build", KERNELS, ids=lambda f: f.__name__)
def test_roundtrips(build):
    method = build()
    validate(method)
    assert roundtrips(method)
