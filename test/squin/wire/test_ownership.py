"""Reject duplicated quantum tuple fields and overlapping register borrows."""

import pytest
from kirin import ir, types
from kirin.dialects import py, func
from kirin.ir.exception import ValidationErrorGroup

from bloqade.squin.wire import Gate, GateKind, WireType, RegisterType, stmts, kernel
from bloqade.squin.passes.wire_to_squin import WireToSquin
from bloqade.squin.analysis.validation.wire import WireValidation


def method(block, inputs=()):
    """Build a wire method with the type of its actual return value."""
    output = block.last_stmt.value.type
    code = func.Function(
        sym_name="ownership",
        body=ir.Region(block),
        signature=func.Signature(inputs=inputs, output=output),
    )
    return ir.Method(dialects=kernel, code=code)


def tuple_uses(indices, *, nested=False, dynamic=False, erased=False):
    """Build a tuple whose quantum field has the requested extraction uses."""
    block = ir.Block(argtypes=(types.Any, types.Int) if dynamic else (types.Any,))
    wire, zero = stmts.Alloc(), py.Constant(0)
    packed = py.tuple.New((wire.result, zero.result))
    block.stmts.extend([wire, zero, packed])
    if nested:
        outer = py.tuple.New((zero.result, packed.result))
        one = py.Constant(1)
        inner = py.GetItem(outer.result, one.result)
        inner.result.type = packed.result.type
        block.stmts.extend([outer, one, inner])
        value = inner.result
    else:
        value = packed.result
    for index in indices:
        at = py.Constant(index)
        got = py.GetItem(value, block.args[1] if dynamic else at.result)
        quantum = index in (0, -2)
        got.result.type = types.Any if erased else (WireType if quantum else types.Int)
        block.stmts.extend([at, got])
        if quantum:
            block.stmts.append(stmts.Free(got.result))
    none = py.Constant(None)
    block.stmts.extend([none, func.Return(none.result)])
    return method(block, (types.Int,) if dynamic else ())


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("indices", [(0, 0), (0, -2), (1,)])
def test_each_quantum_tuple_field_requires_one_consumption(indices, nested):
    with pytest.raises(ValidationErrorGroup, match="tuple field"):
        WireValidation().check(tuple_uses(indices, nested=nested))


@pytest.mark.parametrize("nested", [False, True])
def test_classical_tuple_fields_allow_repeated_reads(nested):
    WireValidation().check(tuple_uses((1, 0, 1), nested=nested))


def test_a_quantum_tuple_requires_a_static_field_selection():
    with pytest.raises(ValidationErrorGroup, match="constant index"):
        WireValidation().check(tuple_uses((0,), dynamic=True))


def test_reverse_conversion_checks_ownership_before_rewriting():
    broken = tuple_uses((0, 0))
    before = broken.code.print_str()
    with pytest.raises(ValidationErrorGroup, match="tuple field"):
        WireToSquin().emit(broken)
    assert broken.code.print_str() == before


def borrows(*, offset=None, sequential=False):
    """Borrow the register positions `i` and `j`, or `i` and `i + offset`."""
    block = ir.Block(argtypes=(types.Any, RegisterType, types.Int, types.Int))
    _, register, i, j = block.args
    if offset is not None:
        number = py.Constant(offset)
        add = py.Add(i, number.result)
        add.result.type = types.Int
        block.stmts.extend([number, add])
        j = add.result
    first = stmts.Borrow(register, i)
    block.stmts.append(first)
    if sequential:
        restored = stmts.Release(first.register_out, i, first.wire)
        second = stmts.Borrow(restored.register_out, j)
        final = stmts.Release(second.register_out, j, second.wire)
        block.stmts.extend([restored, second, final])
    else:
        second = stmts.Borrow(first.register_out, j)
        gate = Gate(GateKind.CX, (first.wire, second.wire))
        control, target = gate.outputs
        back = stmts.Release(second.register_out, j, target)
        final = stmts.Release(back.register_out, i, control)
        block.stmts.extend([second, gate, back, final])
    block.stmts.append(func.Return(final.register_out))
    return method(block, (RegisterType, types.Int, types.Int))


def test_unrelated_symbols_can_borrow_together():
    WireValidation().check(borrows())


def test_equal_index_expressions_cannot_borrow_twice():
    with pytest.raises(ValidationErrorGroup, match="already out of its register"):
        WireValidation().check(borrows(offset=0))


@pytest.mark.parametrize("offset", [-2, -1, 1, 2])
def test_borrows_at_nonzero_offsets_pass(offset):
    WireValidation().check(borrows(offset=offset))


def test_sequential_borrows_need_no_separation_proof():
    WireValidation().check(borrows(sequential=True))


def test_tuple_construction_cannot_hide_quantum_fields_in_any():
    broken = tuple_uses((0,))
    packed = next(node for node in broken.code.walk() if isinstance(node, py.tuple.New))
    packed.result.type = types.Any
    with pytest.raises(ValidationErrorGroup, match="preserve every quantum field"):
        WireValidation().check(broken)


def test_tuple_extraction_cannot_erase_quantum_ownership():
    with pytest.raises(ValidationErrorGroup, match="preserve the quantum field type"):
        WireValidation().check(tuple_uses((0,), erased=True))


def test_function_outputs_cannot_erase_quantum_ownership():
    block = ir.Block(argtypes=(types.Any,))
    wire = stmts.Alloc()
    block.stmts.extend([wire, func.Return(wire.result)])
    broken = method(block)
    broken.code.signature = func.Signature(inputs=(), output=types.Any)
    with pytest.raises(ValidationErrorGroup, match="boundary type must preserve"):
        WireValidation().check(broken)


def test_quantum_tuple_parameters_require_explicit_flattening():
    kind = types.Generic(tuple, WireType, types.Int)
    block = ir.Block(argtypes=(types.Any, kind))
    block.stmts.append(func.Return(block.args[1]))
    with pytest.raises(ValidationErrorGroup, match="parameters must be separate"):
        WireValidation().check(method(block, (kind,)))


def test_an_impossible_result_type_cannot_hide_an_allocation():
    block = ir.Block(argtypes=(types.Any,))
    wire, none = stmts.Alloc(), py.Constant(None)
    wire.result.type = types.Bottom
    block.stmts.extend([wire, none, func.Return(none.result)])
    with pytest.raises(ValidationErrorGroup, match="impossible type Bottom"):
        WireValidation().check(method(block))
