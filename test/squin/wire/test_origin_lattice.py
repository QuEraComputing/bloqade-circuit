"""Check the ordering laws and call identities of wire position validation."""

from itertools import product

from kirin.dialects import py

from bloqade.analysis.indices import IndexExpr
from bloqade.squin.analysis.validation.wire.origins import (
    Origin,
    QubitHandle,
    TupleOrigin,
    HandleOrigin,
    RegisterHandle,
    element_of,
)


def test_origin_join_and_meet_obey_lattice_laws():
    a, b = HandleOrigin(QubitHandle("a")), HandleOrigin(QubitHandle("b"))
    top, bottom = Origin.top(), Origin.bottom()
    values = (
        top,
        bottom,
        a,
        b,
        TupleOrigin((a, b)),
        TupleOrigin((top, b)),
        TupleOrigin((a, bottom)),
        TupleOrigin(()),
    )
    for left, right in product(values, repeat=2):
        assert left.join(right) == right.join(left)
        assert left.meet(right) == right.meet(left)
        assert left.join(left.meet(right)) == left
        assert left.meet(left.join(right)) == left
        assert left.is_subseteq(left.join(right))
        assert left.meet(right).is_subseteq(left)
    for a, b, c in product(values, repeat=3):
        assert a.join(b).join(c) == a.join(b.join(c))
        assert a.meet(b).meet(c) == a.meet(b.meet(c))


def test_tuple_joins_keep_the_fields_that_agree():
    a, b = HandleOrigin(QubitHandle("a")), HandleOrigin(QubitHandle("b"))
    assert TupleOrigin((a, b)).join(TupleOrigin((a, a))) == TupleOrigin(
        (a, Origin.top())
    )


def test_call_results_keep_borrowed_roots_and_distinguish_fresh_roots():
    borrowed = HandleOrigin(QubitHandle("input"))
    fresh = HandleOrigin(QubitHandle("local"))
    outputs = TupleOrigin((borrowed, fresh))
    first = outputs.at_call(py.Constant(0), frozenset({"input"}))
    second = outputs.at_call(py.Constant(0), frozenset({"input"}))
    assert isinstance(first, TupleOrigin) and isinstance(second, TupleOrigin)
    assert first.fields[0] == second.fields[0] == borrowed
    assert first.fields[1].roots().isdisjoint(second.fields[1].roots())


def test_register_origins_resolve_negative_indices_and_reject_invalid_elements():
    register = HandleOrigin(RegisterHandle("register", IndexExpr(3)))
    assert element_of(register, IndexExpr(-1)) == element_of(register, IndexExpr(2))
    assert element_of(register, IndexExpr(3)) == Origin.top()
    assert element_of(register, IndexExpr(-4)) == Origin.top()
    assert element_of(HandleOrigin(QubitHandle("wire")), IndexExpr(0)) == Origin.top()
