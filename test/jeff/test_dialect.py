"""Test the jeff statements, types, and the rules that kirin's analyses need."""

import pytest
from kirin import ir, types
from kirin.dialects import func

from bloqade import jeff
from bloqade.constants import constant_int
from bloqade.jeff.types import qureg, family, is_bit, is_linear, qureg_length
from bloqade.jeff.dialects import stmts

from .build import add, entry, method


def test_register_types_carry_their_length():
    assert qureg(None) == jeff.QuregType
    assert qureg_length(qureg(None)) is None
    assert qureg_length(qureg(types.TypeVar("N"))) is None
    assert qureg_length(qureg(3)) == 3


def test_a_type_outside_the_families_has_none():
    assert family(types.PyClass(str)) is None


def test_a_block_argument_is_no_constant():
    _, (n,) = entry(types.Int)
    assert constant_int(n) is None


def test_region_statements_require_a_yield():
    block, _ = entry()
    zero = add(block, stmts.ConstInt(value=0)).result
    with pytest.raises(TypeError, match="default region"):
        stmts.Switch(zero, (), [], ir.Region(ir.Block([stmts.Return()])))
    with pytest.raises(TypeError, match="before region"):
        stmts.While((), ir.Region(ir.Block([stmts.Return()])), ir.Region())


def test_array_statements_build_and_verify():
    block, _ = entry()
    two = add(block, stmts.ConstInt(value=2)).result
    zero = add(block, stmts.ConstInt(value=0)).result
    zeros = add(block, stmts.IntArrayZero(two)).result
    got = add(block, stmts.IntArrayGet(zeros, zero, bitwidth=32)).result
    ints = add(block, stmts.IntArrayCreate((got, got), bitwidth=32)).result
    x = add(block, stmts.ConstFloat(value=1.5)).result
    floats = add(block, stmts.FloatArrayCreate((x, x))).result
    output = types.Generic(tuple, jeff.IntArrayType, jeff.FloatArrayType)
    mt = method(block, (ints, floats), output)
    mt.verify()
    mt.verify_type()


def test_a_constant_without_a_value_is_no_constant():
    block, _ = entry()
    none = add(block, func.ConstantNone()).result
    assert constant_int(none) is None


def test_bottom_belongs_to_no_type():
    block, _ = entry()
    value = add(block, stmts.ConstInt(value=1)).result
    value.type = types.Bottom
    assert not is_linear(types.Bottom)
    assert not is_bit(value)
    assert family(types.Bottom) is None
