"""Test reference tracking through allocations, calls, indexing, and loops."""

import math
from typing import Any

from kirin import types
from kirin.dialects import py, scf, func, ilist

from bloqade import squin
from bloqade.types import Qubit, QubitType, MeasurementResult
from bloqade.analysis.reference import (
    UNTRACKED,
    Slot,
    Items,
    Whole,
    Unknown,
    Register,
    Positions,
)
from bloqade.squin.analysis.reference import (
    QubitReferenceAnalysis,
)

QUBIT_LIST = ilist.IListType[QubitType, types.Any]


def refs_of(kernel):
    mt = kernel.similar()
    frame, _ = QubitReferenceAnalysis(mt.dialects).run(mt)
    return mt, frame.entries


def statements(mt, kind):
    return [n for n in mt.callable_region.walk() if isinstance(n, kind)]


def returned(refs, call, position=0):
    """Return the root that `call` returns at `position`, as the analysis names it."""
    ref = refs[call.result]
    ref = ref.refs[position] if isinstance(ref, Positions) else ref
    return ref.root


def allocations(mt, refs):
    """Return the register roots of the `qalloc` calls of `mt`, in order."""
    return [returned(refs, n) for n in calls(mt, "qalloc")]


def calls(mt, name):
    return [n for n in statements(mt, func.Invoke) if n.callee.sym_name == name]


# -- kernels -------------------------------------------------------------------


@squin.kernel
def prep(q: Qubit) -> tuple[Qubit, MeasurementResult]:
    squin.h(q)
    r = q
    return r, squin.qubit.measure(r)


@squin.kernel
def maker() -> tuple[Qubit, MeasurementResult]:
    a = squin.qubit.new()
    return a, squin.qubit.measure(a)


@squin.kernel
def through(q: Qubit) -> Qubit:
    return prep(q)[0]


@squin.kernel
def twice() -> tuple[Qubit, Qubit]:
    a = squin.qubit.new()
    return a, a


@squin.kernel
def elements(qs: ilist.IList[Qubit, Any], i: int):
    q = squin.qubit.new()
    made = maker()
    squin.cx(qs[1], qs[-1])
    squin.cx(qs[i], q)
    squin.cx(made[0], q)
    prep(q)
    squin.h(q)
    for _ in range(2):
        squin.h(qs[0])
    return made[1]


@squin.kernel
def sized():
    qs = squin.qalloc(3)
    squin.cx(qs[-1], qs[0])
    squin.broadcast.x([qs[0], qs[2]])
    return squin.qubit.measure(qs[2])


@squin.kernel
def bad_reads():
    qs = squin.qalloc(3)
    squin.broadcast.x(qs[0:2])
    squin.h(qs[5])


@squin.kernel
def swaps_in_loop():
    q = squin.qubit.new()
    p = squin.qubit.new()
    for _ in range(2):
        squin.h(q)
        q = p
    return squin.qubit.measure(q)


@squin.kernel
def rotation(theta: float):
    q = squin.qubit.new()
    squin.rx(theta, q)
    squin.rz(math.pi / 2, q)
    return squin.qubit.measure(q)


# -- the rules -----------------------------------------------------------------


def test_parameters_allocations_and_elements():
    mt, refs = refs_of(elements)
    _, qs, i = mt.callable_region.blocks[0].args
    assert refs[qs] == Register(qs) and refs[i] == UNTRACKED
    cx = calls(mt, "cx")
    assert [refs[v] for v in cx[0].inputs] == [Slot(qs, 1), Slot(qs, -1)]
    (new,) = calls(mt, "new")
    fresh = Whole(returned(refs, new))
    assert [refs[v] for v in cx[1].inputs] == [Slot(qs, i), fresh]
    (made,) = calls(mt, "maker")
    assert [refs[v] for v in cx[2].inputs] == [Whole(returned(refs, made)), fresh]
    assert refs[made.result] == Positions((Whole(returned(refs, made)), UNTRACKED))
    h_prepped, h_loop = calls(mt, "h")
    assert refs[h_prepped.inputs[0]] == fresh  # the qubit lent to prep stays q
    assert refs[h_loop.inputs[0]] == Slot(qs, 0)
    (ret,) = statements(mt, func.Return)
    assert refs[ret.value] == UNTRACKED


def test_static_length_normalizes_constant_indices():
    mt, refs = refs_of(sized)
    (qs,) = allocations(mt, refs)
    (cx,) = calls(mt, "cx")
    assert [refs[v] for v in cx.inputs] == [Slot(qs, 2), Slot(qs, 0)]
    (operands,) = statements(mt, ilist.New)  # the inlined broadcast's operand
    assert refs[operands.result] == Items((Slot(qs, 0), Slot(qs, 2)))


def reason(ref) -> str | None:
    return ref.reason if isinstance(ref, Unknown) else None


def test_unknowns_carry_their_reason():
    mt, refs = refs_of(bad_reads)
    (x,) = calls(mt, "x")
    assert reason(refs[x.inputs[0]]) == "a slice of a register"
    (h,) = calls(mt, "h")
    assert reason(refs[h.inputs[0]]) == "a constant index out of range"


def test_a_qubit_swapped_by_a_loop_is_unknown():
    """A loop-carried reference becomes unknown when the body changes its root."""
    mt, refs = refs_of(swaps_in_loop)
    (loop,) = statements(mt, scf.For)
    carried = [a for a in loop.body.blocks[0].args[1:] if a.type.is_subseteq(QubitType)]
    assert "a value carried by a loop or branch" in [reason(refs[a]) for a in carried]
    assert all(isinstance(refs[a], (Whole, Unknown)) for a in carried)


# -- what calls hand back ----------------------------------------------------------


def test_a_lent_qubit_handed_back_is_the_callers():
    """Nested calls preserve the root of a returned argument."""
    mt, refs = refs_of(through)
    (q,) = mt.callable_region.blocks[0].args[1:]
    (ret,) = statements(mt, func.Return)
    assert refs[ret.value] == Whole(q)
    (call,) = calls(mt, "prep")
    assert refs[call.result] == Positions((Whole(q), UNTRACKED))


def test_an_allocation_made_by_a_call_is_rooted_at_the_call():
    mt, refs = refs_of(elements)
    (made,) = calls(mt, "maker")
    assert refs[made.result] == Positions((Whole(returned(refs, made)), UNTRACKED))


@squin.kernel
def reads_twice():
    pair = twice()
    squin.cx(pair[0], pair[1])


def test_an_allocation_at_two_positions_is_one_root():
    """The caller sees the same qubit twice, rooted at its first position."""
    mt, refs = refs_of(reads_twice)
    (call,) = calls(mt, "twice")
    (cx,) = calls(mt, "cx")
    first, second = (refs[v] for v in cx.inputs)
    assert first == second == Whole(returned(refs, call))


@squin.kernel
def make_pair() -> ilist.IList[Qubit, Any]:
    return squin.qalloc(2)


@squin.kernel
def reads_made_pair():
    qs = make_pair()
    squin.cx(qs[1], qs[-1])


def test_a_returned_register_keeps_its_static_length():
    """The length of the register inside the callee normalizes a negative index."""
    mt, refs = refs_of(reads_made_pair)
    (cx,) = calls(mt, "cx")
    first, second = (refs[v] for v in cx.inputs)
    assert isinstance(first, Slot) and isinstance(second, Slot)
    assert first.root == second.root
    assert first.index == second.index == 1
    assert repr(first) == "Slot(%qs = make_pair()[0], 1)"


def test_a_recursive_call_hands_its_qubit_back():
    @squin.kernel
    def rec(q: Qubit, n: int) -> Qubit:
        squin.h(q)
        if n > 0:
            r = rec(q, n - 1)
        else:
            r = q
        return r

    mt, refs = refs_of(rec)
    (call,) = calls(mt, "rec")
    assert refs[call.result] == Whole(mt.callable_region.blocks[0].args[1])


def test_unknown_is_one_top_element():
    """Unknown reasons do not affect equality, and a join keeps an unknown's reason."""
    a, b = Unknown("a"), Unknown("b")
    assert a == b and a.is_subseteq(b) and b.is_subseteq(a)
    assert a.join(b) is b and b.join(a) is a
    assert UNTRACKED.join(a) is a and a.join(UNTRACKED) is a


@squin.kernel
def branches(flag: bool):
    a = squin.qubit.new()
    b = squin.qubit.new()
    if flag:
        q = a
        r = a
    else:
        q = a
        r = b
    squin.h(q)
    squin.h(r)


def test_a_branch_keeps_a_reference_that_both_paths_yield():
    mt, refs = refs_of(branches)
    a, _ = calls(mt, "new")
    same, different = (refs[call.inputs[0]] for call in calls(mt, "h"))
    assert same == Whole(returned(refs, a))
    assert reason(different) == "a value carried by a loop or branch"


@squin.kernel
def concatenated():
    a = squin.qubit.new()
    b = squin.qubit.new()
    squin.broadcast.h([a] + [b])


def test_literal_lists_concatenate_item_by_item():
    mt, refs = refs_of(concatenated)
    a, b = (Whole(returned(refs, call)) for call in calls(mt, "new"))
    (add,) = statements(mt, py.binop.Add)
    assert refs[add.result] == Items((a, b))


@squin.kernel
def pick(qs: ilist.IList[Qubit, Any], i: int) -> Qubit:
    return qs[i]


@squin.kernel
def pick_next(qs: ilist.IList[Qubit, Any], i: int) -> Qubit:
    return qs[i + 1]


@squin.kernel
def picks():
    qs = squin.qalloc(3)
    a = squin.qubit.new()
    b = squin.qubit.new()
    squin.h(pick(qs, -1))
    squin.h(pick(qs, 0))
    squin.h(pick([a, b], 1))
    squin.h(pick_next(qs, 0))


def test_a_slot_at_a_parameter_index_takes_the_argument():
    """A slot keeps a parameter index, so the caller's constant resolves it.

    A literal list has no slots, so a read at a parameter index stays unknown.
    """
    mt, refs = refs_of(picks)
    (qs,) = allocations(mt, refs)
    last, first, literal, computed = (refs[h.inputs[0]] for h in calls(mt, "h"))
    assert last == Slot(qs, 2) and first == Slot(qs, 0)
    assert reason(literal) == "a list or tuple read at a runtime index"
    assert reason(computed) == "an item at an index that the callee computes"


def test_a_function_runs_in_terms_of_its_own_parameters():
    mt = pick.similar()
    _, result = QubitReferenceAnalysis(mt.dialects).run(mt)
    qs, i = mt.callable_region.blocks[0].args[1:]
    assert result == Slot(qs, i)
