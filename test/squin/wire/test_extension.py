"""Test a dialect outside squin that adds its own statements to wire programs.

The test dialect `test.ext` has a reference statement on qubits and an allocation.
Its wire dialect `test.ext.wire` holds their wire forms. The test dialect registers
its emission under `emit.squin_wire`, and each wire form carries `ReferenceForm`.
This is the same work that a dialect such as Gemini does.
"""

import math
from typing import Any

import pytest
from kirin import ir, types, interp, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin, native
from bloqade.types import Qubit, QubitType
from bloqade.squin.wire import (
    Threads,
    WireType,
    ReferenceForm,
    ThreadsInOrder,
    stmts as wire,
)
from bloqade.squin.emit.wire import EmitWire, WireFrame
from bloqade.squin.wire.group import reference_kernel
from bloqade.squin.wire.errors import WireConversionError
from bloqade.native.dialects.gate import stmts as native_stmts
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin
from bloqade.squin.passes.wire_rotations import merge_native_rotations
from bloqade.squin.analysis.validation.wire import WireValidation

reference = ir.Dialect("test.ext")
linear = ir.Dialect("test.ext.wire")


@statement(dialect=reference)
class Mark(ir.Statement):
    """Read a list of qubits and return an integer, like a measurement."""

    name = "mark"
    traits = frozenset({lowering.FromPythonCall()})
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, types.Any])
    tag: int = info.attribute()
    result: ir.ResultValue = info.result(types.Int)


@statement(dialect=reference)
class Fresh(ir.Statement):
    """Allocate one qubit at a site, like Gemini's `new_at`."""

    name = "fresh"
    traits = frozenset({lowering.FromPythonCall()})
    site: ir.SSAValue = info.argument(types.Int)
    result: ir.ResultValue = info.result(QubitType)


@lowering.wraps(Mark)
def mark(qubits: ilist.IList[Qubit, Any], *, tag: int) -> int: ...


@lowering.wraps(Fresh)
def fresh(site: int) -> Qubit: ...


class MarkReference(ReferenceForm):
    """Rebuild `Mark` on the list of the wires of `WireMark`."""

    def rebuild(self, node: ir.Statement) -> tuple[ir.SSAValue, ...]:
        """Insert `Mark` and return its integer result."""
        assert isinstance(node, WireMark)
        listed = ilist.New(values=tuple(node.wires), elem_type=QubitType)
        listed.insert_before(node)
        made = Mark(listed.result, tag=node.tag)
        made.insert_before(node)
        return (made.result,)


class FreshReference(ReferenceForm):
    """Rebuild `Fresh` at the site of `WireFresh`."""

    def rebuild(self, node: ir.Statement) -> tuple[ir.SSAValue, ...]:
        """Insert `Fresh` and return its qubit."""
        assert isinstance(node, WireFresh)
        made = Fresh(node.site)
        made.insert_before(node)
        return (made.result,)


@statement(dialect=linear, init=False)
class WireMark(ir.Statement):
    """Read the qubits of `wires`, keep them, and return an integer."""

    name = "wire_mark"
    traits = frozenset({ThreadsInOrder("wires"), MarkReference()})
    wires: tuple[ir.SSAValue, ...] = info.argument(WireType)
    tag: int = info.attribute()

    def __init__(self, wires: tuple[ir.SSAValue, ...], tag: int) -> None:
        """Build the statement on `wires` with the tag `tag`."""
        super().__init__(
            args=wires,
            result_types=(*(WireType for _ in wires), types.Int),
            args_slice={"wires": slice(0, len(wires))},
            attributes={"tag": ir.PyAttr(tag)},
        )


@statement(dialect=linear)
class WireFresh(ir.Statement):
    """Allocate one qubit at `site` and return its wire."""

    name = "wire_fresh"
    traits = frozenset({FreshReference()})
    site: ir.SSAValue = info.argument(types.Int)
    result: ir.ResultValue = info.result(WireType)


@statement(dialect=linear, init=False)
class Opaque(ir.Statement):
    """Keep the qubits of `wires`, with no way back to reference squin."""

    name = "opaque"
    traits = frozenset({ThreadsInOrder("wires")})
    wires: tuple[ir.SSAValue, ...] = info.argument(WireType)

    def __init__(self, wires: tuple[ir.SSAValue, ...]) -> None:
        """Build the statement on `wires`."""
        super().__init__(
            args=wires,
            result_types=tuple(WireType for _ in wires),
            args_slice={"wires": slice(0, len(wires))},
        )


@reference.register(key="emit.squin_wire")
class Emission(interp.MethodTable):
    """Emit the wire forms of the test statements."""

    @interp.impl(Mark)
    def mark(self, emit: EmitWire, frame: WireFrame, stmt: Mark):
        """Emit `WireMark` on the wires of the marked qubits."""
        locations = emit.qubits_of(frame, stmt.qubits, stmt)
        made = emit.operate(
            frame, locations, lambda wires: WireMark(wires, tag=stmt.tag)
        )
        return (made.results[-1],)

    @interp.impl(Fresh)
    def fresh(self, emit: EmitWire, frame: WireFrame, stmt: Fresh):
        """Emit `WireFresh` and record its wire as a new qubit."""
        site = emit.classical_value(frame, frame.get(stmt.site))
        return (emit.new_qubit(frame, frame.push(WireFresh(site)).result),)


kernel = reference_kernel.add(reference)


@kernel
def barrier():
    qs = squin.qalloc(2)
    native.rx(math.pi / 3, qs[0])
    mark([qs[0]], tag=7)
    native.rx(-math.pi / 3, qs[0])
    native.rx(math.pi / 5, qs[1])
    native.rx(-math.pi / 5, qs[1])


@kernel
def allocated():
    q = fresh(3)
    native.rx(math.pi / 3, q)
    native.rx(-math.pi / 3, q)
    mark([q], tag=1)


def statements(method: ir.Method) -> list[ir.Statement]:
    """Return every statement of `method`, including those in nested regions."""
    return list(method.callable_region.walk())


def test_a_wire_form_of_another_dialect_survives_the_round_trip():
    wired = SquinToWire((linear,)).emit(barrier)
    WireValidation().check(wired)
    (made,) = (n for n in statements(wired) if isinstance(n, WireMark))
    assert len(made.wires) == 1 and made.has_trait(Threads)
    back = WireToSquin((linear,)).emit(wired)
    back.verify()
    assert linear not in back.dialects.data
    (marked,) = (n for n in statements(back) if isinstance(n, Mark))
    assert marked.tag == 7


def test_a_wire_form_ends_rotation_runs_on_its_qubits_only():
    merged = merge_native_rotations(barrier, (linear,))
    rotations = [n for n in statements(merged) if isinstance(n, native_stmts.R)]
    assert len(rotations) == 2
    assert any(isinstance(n, Mark) for n in statements(merged))


def test_an_allocation_of_another_dialect_becomes_a_new_wire():
    wired = SquinToWire((linear,)).emit(allocated)
    WireValidation().check(wired)
    assert any(isinstance(n, WireFresh) for n in statements(wired))
    assert any(isinstance(n, wire.Free) for n in statements(wired))
    merged = merge_native_rotations(allocated, (linear,))
    assert not any(isinstance(n, native_stmts.R) for n in statements(merged))
    assert [type(n) for n in statements(merged) if n.dialect is reference] == [
        Fresh,
        Mark,
    ]


def test_a_missing_wire_dialect_names_the_option():
    with pytest.raises(WireConversionError, match="wire_dialects"):
        SquinToWire().emit(barrier)


def test_merging_without_a_wire_form_returns_the_kernel_under_no_raise():
    assert merge_native_rotations(barrier, no_raise=True) is barrier
    with pytest.raises(WireConversionError):
        merge_native_rotations(barrier)


def test_a_wire_statement_without_a_reference_form_names_the_trait():
    wired = SquinToWire((linear,)).emit(barrier)
    (made,) = (n for n in statements(wired) if isinstance(n, WireMark))
    bare = Opaque(tuple(made.wires))
    bare.insert_before(made)
    for old, new in zip(made.results, bare.results):
        old.replace_by(new)
    made.delete(safe=False)
    with pytest.raises(ValidationErrorGroup, match="needs a ReferenceForm trait"):
        WireToSquin((linear,)).emit(wired)


def test_a_reference_form_must_return_one_value_per_new_result(monkeypatch):
    monkeypatch.setattr(MarkReference, "rebuild", lambda self, node: ())
    wired = SquinToWire((linear,)).emit(barrier)
    with pytest.raises(WireConversionError, match="returned 0 values for 1"):
        WireToSquin((linear,)).emit(wired)
