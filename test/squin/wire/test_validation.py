"""Test that the kirin validation suite `WireValidation` catches broken wire squin."""

from typing import Any

import pytest
from kirin import ir
from kirin.dialects import py, scf, ilist
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.types import MeasurementResult
from bloqade.squin.wire import Gate, GateKind, stmts as wire_stmts
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.analysis.validation.wire import (
    WireValidation,
    BorrowValidation,
    LinearityValidation,
    StructureValidation,
)


@squin.kernel
def ladder() -> ilist.IList[MeasurementResult, Any]:
    qs = squin.qalloc(3)
    for i in range(2):
        squin.cx(qs[i], qs[i + 1])
    return squin.broadcast.measure(qs)


def first(mt: ir.Method, kind: type[ir.Statement]) -> ir.Statement:
    """Return the first statement of the class `kind` in `mt`, bodies included."""
    return next(node for node in mt.callable_region.walk() if isinstance(node, kind))


def errors(validation, mt: ir.Method) -> list[str]:
    """Return the messages of the errors that `validation` finds in `mt`."""
    return [str(error) for error in validation.run(mt)[1]]


def test_the_converter_output_passes_every_check():
    WireValidation().check(SquinToWire().emit(ladder))


def test_a_wire_with_two_uses_breaks_linearity():
    wired = SquinToWire().emit(ladder)
    alloc = first(wired, wire_stmts.AllocRegister)
    wire_stmts.FreeRegister(alloc.result).insert_after(alloc)
    with pytest.raises(ValidationErrorGroup, match="linearity"):
        WireValidation().check(wired)


def test_a_loop_body_that_reads_an_outer_wire_breaks_linearity():
    wired = SquinToWire().emit(ladder)
    loop = first(wired, scf.For)
    carried = loop.body.blocks[0].args[1]
    carried.replace_by(loop.initializers[0])
    found = errors(LinearityValidation(), wired)
    assert any("crosses into the body" in message for message in found)


def test_a_slot_borrowed_twice_breaks_the_borrow_rule():
    wired = SquinToWire().emit(ladder)
    borrow = first(wired, wire_stmts.Borrow)
    again = wire_stmts.Borrow(borrow.register_out, borrow.index)
    again.insert_after(borrow)
    found = errors(BorrowValidation(), wired)
    assert any("already borrowed" in message for message in found)


def test_a_release_without_a_borrow_breaks_the_borrow_rule():
    wired = SquinToWire().emit(ladder)
    alloc = first(wired, wire_stmts.AllocRegister)
    zero = py.Constant(0)
    zero.insert_after(alloc)
    fresh = wire_stmts.Alloc()
    fresh.insert_after(zero)
    release = wire_stmts.Release(alloc.result, zero.result, fresh.result)
    release.insert_after(fresh)
    found = errors(BorrowValidation(), wired)
    assert any("matching borrowed index" in message for message in found)


def test_a_register_that_leaves_with_a_borrowed_slot_breaks_the_borrow_rule():
    wired = SquinToWire().emit(ladder)
    alloc = first(wired, wire_stmts.AllocRegister)
    zero = py.Constant(0)
    zero.insert_after(alloc)
    borrow = wire_stmts.Borrow(alloc.result, zero.result)
    borrow.insert_after(zero)
    wire_stmts.Free(borrow.wire).insert_after(borrow)
    loop = first(wired, scf.For)
    loop.initializers = (borrow.register_out,)
    found = errors(BorrowValidation(), wired)
    assert any("borrowed slots" in message for message in found)


def test_a_gate_on_a_classical_value_breaks_the_types():
    wired = SquinToWire().emit(ladder)
    alloc = first(wired, wire_stmts.AllocRegister)
    number = py.Constant(1)
    number.insert_after(alloc)
    gate = Gate(GateKind.H, (number.result,))
    gate.insert_after(number)
    assert errors(StructureValidation(), wired)
