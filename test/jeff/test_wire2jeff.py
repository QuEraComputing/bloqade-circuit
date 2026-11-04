"""Check direct wire emission and the borrowed-parameter return convention."""

import pytest
from kirin import types
from kirin.dialects import func
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.jeff import WireToJeff, JeffToSquin
from bloqade.types import Qubit
from bloqade.jeff.types import WireType
from bloqade.jeff.dialects import stmts
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin

from .helpers import simulate, as_python, roundtrips


@squin.kernel
def tick(q: Qubit) -> int:
    squin.x(q)
    return 7


@squin.kernel
def program(n: int, flag: bool):
    qs = squin.qalloc(2)
    tag = tick(qs[0])
    for _ in range(n):
        squin.x(qs[1])
    if flag:
        squin.swap(qs[0], qs[1])
    return squin.broadcast.measure(qs), tag


@pytest.mark.parametrize("n, flag", [(0, False), (1, True), (2, True)])
def test_direct_emission_needs_no_reference_conversion(monkeypatch, n, flag):
    wire = SquinToWire().emit(program)
    before = wire.code.print_str()

    def forbidden(*args, **kwargs):
        raise AssertionError("Direct emission must consume the supplied wire program.")

    monkeypatch.setattr(SquinToWire, "emit", forbidden)
    monkeypatch.setattr(WireToSquin, "emit", forbidden)
    emitter = WireToJeff()
    first = emitter.emit(wire)
    second = emitter.emit(wire)
    assert first.code.print_str() == second.code.print_str()
    assert wire.code.print_str() == before
    assert roundtrips(first)
    monkeypatch.undo()
    back = JeffToSquin().emit(first)
    assert as_python(simulate(back, n, flag)) == as_python(simulate(program, n, flag))
    call = next(node for node in first.code.walk() if isinstance(node, stmts.Call))
    assert tuple(value.type for value in call.results) == (types.Int, WireType)


def test_direct_emission_validates_the_supplied_wire_program():
    wire = SquinToWire().emit(program)
    call = next(node for node in wire.code.walk() if isinstance(node, func.Invoke))
    call.result.type = types.Any
    before = wire.code.print_str()
    with pytest.raises(ValidationErrorGroup):
        WireToJeff().emit(wire)
    assert wire.code.print_str() == before
