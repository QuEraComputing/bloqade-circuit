"""Every jeff operation the dialect models emits, reloads and re-emits
byte for byte, including the ones no lowering produces: Pauli-product
rotations, register creation, slices, splits and joins, float functions
and float arrays."""

from kirin import types

from bloqade import jeff
from bloqade.jeff.dialects import stmts

from .build import add, entry, method, validate
from .helpers import roundtrips


def test_register_surgery_and_pauli_rotation_round_trip():
    block, _ = entry()
    wires = [add(block, stmts.Alloc()).result for _ in range(4)]
    angle = add(block, stmts.ConstFloat(value=0.25)).result
    rotated = add(
        block, stmts.Ppr(tuple(wires[:2]), (wires[2],), angle, pauli_string=("x", "z"))
    ).results
    register = add(block, stmts.RegCreate((*rotated, wires[3]))).result
    one = add(block, stmts.ConstInt(value=1)).result
    two = add(block, stmts.ConstInt(value=2)).result
    sliced = add(block, stmts.ExtractSlice(register, one, two))
    whole = add(
        block, stmts.InsertSlice(sliced.result_reg, one, sliced.slice_reg)
    ).result
    split = add(block, stmts.RegSplit(whole, two))
    joined = add(block, stmts.RegJoin(split.before, split.after)).result
    measured = add(block, stmts.RegLength(joined))
    zero = add(block, stmts.ConstInt(value=0)).result
    taken = add(block, stmts.Extract(measured.result_reg, zero))
    bit = add(block, stmts.Measure(taken.wire)).bit
    add(block, stmts.RegFreeZero(taken.result_reg))
    mt = method(
        block, (bit, measured.length), types.Generic(tuple, types.Bool, types.Int)
    )
    validate(mt)
    assert roundtrips(mt)


def test_float_functions_and_arrays_round_trip():
    block, _ = entry()
    x = add(block, stmts.ConstFloat(value=2.0)).result
    y = add(block, stmts.ConstFloat(value=0.5)).result
    root = add(block, stmts.FloatSqrt(x)).result
    angle = add(block, stmts.FloatAtan2(root, y)).result
    least = add(block, stmts.FloatMin(angle, x)).result
    is_nan = add(block, stmts.FloatIsNan(least)).result
    three = add(block, stmts.ConstInt(value=3)).result
    zero = add(block, stmts.ConstInt(value=0)).result
    zeros = add(block, stmts.FloatArrayZero(three)).result
    filled = add(block, stmts.FloatArraySet(zeros, zero, least)).result
    read = add(block, stmts.FloatArrayGet(filled, zero)).result
    built = add(block, stmts.FloatArrayCreate((read, x))).result
    count = add(block, stmts.FloatArrayLen(built)).result
    consts = add(block, stmts.FloatArrayConst(values=(1.5, -2.5))).result
    bits = add(block, stmts.IntArrayConst(values=(1, 0, 1), bitwidth=1)).result
    bit_count = add(block, stmts.IntArrayLen(bits)).result
    total = add(block, stmts.IntAdd(count, bit_count)).result
    magnitude = add(block, stmts.IntAbs(total)).result
    first = add(block, stmts.FloatArrayGet(consts, zero)).result
    mt = method(
        block,
        (is_nan, magnitude, first),
        types.Generic(tuple, types.Bool, types.Int, types.Float),
    )
    validate(mt)
    assert roundtrips(mt)


def test_reset_and_zero_arrays_round_trip():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    (w,) = add(block, stmts.Reset(w)).results
    m = add(block, stmts.MeasureNd(w))
    add(block, stmts.Free(m.result_wire))
    three = add(block, stmts.ConstInt(value=3)).result
    ints = add(block, stmts.IntArrayZero(three)).result
    floats = add(block, stmts.FloatArrayZero(three)).result
    output = types.Generic(tuple, types.Bool, jeff.IntArrayType, jeff.FloatArrayType)
    mt = method(block, (m.bit, ints, floats), output)
    validate(mt)
    assert roundtrips(mt)
