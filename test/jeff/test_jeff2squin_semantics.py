"""Semantics of converted programs, checked by simulating the squin kernel on
pyqrack: the conversion must preserve what the jeff program computes, not only
produce valid squin IR."""

import math

import pytest
from kirin import types

from bloqade import jeff
from bloqade.jeff import JeffToSquin
from bloqade.jeff.dialects import stmts

from . import test_roundtrip as tr
from .build import add, entry, method
from .helpers import SHOTS, simulate, as_python, one_wire_program


def run(jeff_method, *args):
    return simulate(JeffToSquin().emit(jeff_method), *args)


def shots(jeff_method, count=SHOTS) -> list:
    converted = JeffToSquin().emit(jeff_method)
    return [simulate(converted) for _ in range(count)]


# -- the roundtrip kernels, each against what its circuit must produce -------


def test_bell_is_correlated():
    assert all(a == b for a, b in map(as_python, shots(tr.bell())))


@pytest.mark.parametrize(
    "build, expected",
    [
        (tr.rotation, 0),  # rz on |0>
        (tr.nested_loop, 0),  # h^4 = identity
        (tr.float_sweep, 0),  # rz on |0>
        (tr.with_call, 1),  # x through a call
        (tr.register, None),
        (tr.register_surgery, None),
    ],
    ids=lambda x: x.__name__ if callable(x) else repr(x),
)
def test_deterministic_kernel(build, expected):
    for outcome in shots(build()):
        assert (None if outcome is None else int(outcome)) == expected


def test_counted_loop_is_superposition():
    assert {int(b) for b in shots(tr.counted_loop(), 32)} == {0, 1}  # h^3 = h


def test_switch_after_measurement_leaves_the_bit():
    # bit 1 is measured before the switch, so it stays 0 whatever bit 0 is
    for m0, m1 in map(as_python, shots(tr.feedforward())):
        assert m1 == 0 and m0 in (0, 1)


# -- adjoint and controlled rotations ---------------------------------------


def gate(block, wire, name, *params, controls=(), adjoint=False):
    g = add(
        block,
        stmts.Gate(
            (wire,), tuple(controls), tuple(params), gate_name=name, adjoint=adjoint
        ),
    )
    return g.results


def test_adjoint_rotation_inverts():
    # h; rz(pi/2); rz(pi/2)^-1; h is the identity, so the bit is always 0
    def fill(block, w):
        a = add(block, stmts.ConstFloat(value=math.pi / 2)).result
        (w,) = gate(block, w, "h")
        (w,) = gate(block, w, "rz", a)
        (w,) = gate(block, w, "rz", a, adjoint=True)
        (w,) = gate(block, w, "h")
        return w

    assert all(int(b) == 0 for b in shots(one_wire_program(fill)))


def test_adjoint_u_inverts():
    def fill(block, w):
        theta = add(block, stmts.ConstFloat(value=1.1)).result
        phi = add(block, stmts.ConstFloat(value=0.4)).result
        lam = add(block, stmts.ConstFloat(value=2.3)).result
        (w,) = gate(block, w, "u", theta, phi, lam)
        (w,) = gate(block, w, "u", theta, phi, lam, adjoint=True)
        return w

    assert all(int(b) == 0 for b in shots(one_wire_program(fill)))


# -- register inserts that move qubits between slots -------------------------


def two_slot_program(permute):
    """Flip slot 0 of a 2-register, `permute(block, reg) -> reg`, then measure
    both slots."""
    block, _ = entry()
    two = add(block, stmts.ConstInt(value=2)).result
    zero = add(block, stmts.ConstInt(value=0)).result
    one = add(block, stmts.ConstInt(value=1)).result
    reg = add(block, stmts.RegAlloc(two)).result
    e = add(block, stmts.Extract(reg, zero))
    (flipped,) = gate(block, e.wire, "x")
    reg = add(block, stmts.Insert(e.result_reg, zero, flipped)).result
    reg = permute(block, reg)
    f0 = add(block, stmts.Extract(reg, zero))
    f1 = add(block, stmts.Extract(f0.result_reg, one))
    m0 = add(block, stmts.MeasureNd(f0.wire))
    m1 = add(block, stmts.MeasureNd(f1.wire))
    add(block, stmts.Free(m0.result_wire))
    add(block, stmts.Free(m1.result_wire))
    add(block, stmts.RegFree(f1.result_reg))
    out = add(block, stmts.IntArrayCreate((m0.bit, m1.bit), bitwidth=1))
    return method(block, out.result, jeff.IntArrayType, name="perm")


def test_insert_back_in_place_is_identity():
    assert as_python(run(two_slot_program(lambda block, reg: reg))) == [1, 0]


def test_insert_swapping_qubit_refs():
    def swap(block, reg):
        zero = add(block, stmts.ConstInt(value=0)).result
        one = add(block, stmts.ConstInt(value=1)).result
        e0 = add(block, stmts.Extract(reg, zero))
        e1 = add(block, stmts.Extract(e0.result_reg, one))
        reg = add(block, stmts.Insert(e1.result_reg, zero, e1.wire)).result
        return add(block, stmts.Insert(reg, one, e0.wire)).result

    assert as_python(run(two_slot_program(swap))) == [0, 1]


def test_insert_fresh_qubit_into_emptied_slot():
    def replace(block, reg):
        zero = add(block, stmts.ConstInt(value=0)).result
        e0 = add(block, stmts.Extract(reg, zero))
        add(block, stmts.Free(e0.wire))
        fresh = add(block, stmts.Alloc()).result
        return add(block, stmts.Insert(e0.result_reg, zero, fresh)).result

    assert as_python(run(two_slot_program(replace))) == [0, 0]


def test_insert_slice_rotating_register():
    def rotate(block, reg):
        # move slot 0 to the end: extract [0:1], insert at 1 after extracting [1:2]
        zero = add(block, stmts.ConstInt(value=0)).result
        one = add(block, stmts.ConstInt(value=1)).result
        head = add(block, stmts.ExtractSlice(reg, zero, one))
        tail = add(block, stmts.ExtractSlice(head.result_reg, one, one))
        reg = add(
            block, stmts.InsertSlice(tail.result_reg, zero, tail.slice_reg)
        ).result
        return add(block, stmts.InsertSlice(reg, one, head.slice_reg)).result

    assert as_python(run(two_slot_program(rotate))) == [0, 1]


# -- classical corners --------------------------------------------------------


def test_int_not_is_bitwise_on_wide_ints():
    block, _ = entry()
    five = add(block, stmts.ConstInt(value=5)).result
    inverted = add(block, stmts.IntNot(five)).result
    assert run(method(block, inverted, types.Int, name="inv")) == ~5


def test_int_not_is_logical_on_bits():
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    m = add(block, stmts.MeasureNd(w))
    add(block, stmts.Free(m.result_wire))
    negated = add(block, stmts.IntNot(m.bit)).result
    assert run(method(block, negated, types.Bool, name="notbit")) is True
