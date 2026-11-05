"""Check the ordering laws and call roots of the register place lattice."""

from itertools import product

from kirin.dialects import py

from bloqade.analysis.indices import Slice, IndexExpr
from bloqade.squin.analysis.validation.wire.registers import (
    Moved,
    Place,
    Fields,
    Borrowed,
    Register,
    Standalone,
    element,
    position,
)


def places() -> tuple[Place, ...]:
    """Return a set of places that covers every form of the lattice."""
    a, b = Standalone("a"), Standalone("b")
    top, bottom = Place.top(), Place.bottom()
    hole = Borrowed(Slice(IndexExpr(0), 1, IndexExpr(1)), a)
    moved = Moved(Slice(IndexExpr(1), 1, IndexExpr(1)))
    registers = tuple(
        Register(root, length, frozenset(holes))
        for root in (None, "r", "s")
        for length in (None, IndexExpr(2))
        for holes in ((), (hole,), (moved,))
    )
    return (
        top,
        bottom,
        a,
        b,
        Fields((a, b)),
        Fields((top, b)),
        Fields((a, bottom)),
        Fields(()),
        *registers,
    )


def test_place_join_and_meet_obey_lattice_laws():
    values = places()
    for left, right in product(values, repeat=2):
        assert left.join(right) == right.join(left)
        assert left.meet(right) == right.meet(left)
        assert left.join(left.meet(right)) == left
        assert left.meet(left.join(right)) == left
        assert left.is_subseteq(left.join(right))
        assert left.meet(right).is_subseteq(left)
        assert Place.bottom().is_subseteq(left) and left.is_subseteq(Place.top())


def test_place_join_and_meet_are_associative():
    values = places()[:10]
    for a, b, c in product(values, repeat=3):
        assert a.join(b).join(c) == a.join(b.join(c))
        assert a.meet(b).meet(c) == a.meet(b.meet(c))


def test_tuple_joins_keep_the_fields_that_agree():
    a, b = Standalone("a"), Standalone("b")
    assert Fields((a, b)).join(Fields((a, a))) == Fields((a, Place.top()))


def test_call_results_keep_passed_roots_and_distinguish_new_roots():
    passed, local = Standalone("input"), Standalone("local")
    outputs = Fields((passed, local))
    first = outputs.at_call(py.Constant(0), frozenset({"input"}))
    second = outputs.at_call(py.Constant(0), frozenset({"input"}))
    assert isinstance(first, Fields) and isinstance(second, Fields)
    assert first.items[0] == second.items[0] == passed
    assert first.items[1].roots().isdisjoint(second.items[1].roots())


def test_register_positions_count_negative_indices_from_the_end():
    register = Register("register", IndexExpr(3))
    assert position(register, IndexExpr(-1)) == IndexExpr(2)
    assert element(register, IndexExpr(-1)) == Place.top()
    assert element(register, IndexExpr(3)) == Place.top()
    assert element(register, IndexExpr(-4)) == Place.top()
    assert element(Register(None, IndexExpr(3)), IndexExpr(0)) == Place.top()
