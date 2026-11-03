from kirin import ir, types
from kirin.analysis import const
from kirin.dialects import py, ilist

from bloqade import squin
from bloqade.stim.passes.hint_const_in_loops import HintLen, HintPureFromConcrete


def test_hint_len_replaces_unknown_hint():
    """Check that HintLen reads the length from the type over an Unknown hint."""
    measurements = ir.TestValue(type=ilist.IListType[types.Any, types.Literal(5)])
    stmt = py.Len(measurements)
    stmt.result.hints["const"] = const.Unknown()

    assert HintLen().rewrite_Statement(stmt).has_done_something
    assert stmt.result.hints["const"] == const.Value(5)


def test_hint_pure_from_concrete_replaces_unknown_hint():
    """Check that HintPureFromConcrete folds constant operands over an Unknown hint."""
    lhs = py.Constant(2)
    rhs = py.Constant(3)
    lhs.result.hints["const"] = const.Value(2)
    rhs.result.hints["const"] = const.Value(3)
    stmt = py.Add(lhs.result, rhs.result)
    stmt.result.hints["const"] = const.Unknown()

    rule = HintPureFromConcrete(squin.kernel)
    assert rule.rewrite_Statement(stmt).has_done_something
    assert stmt.result.hints["const"] == const.Value(5)
