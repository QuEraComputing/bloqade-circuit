"""Test index expressions, the alias check and Python slice semantics."""

from kirin import ir
from kirin.dialects import py

from bloqade import squin
from bloqade.analysis.indices import (
    Iter,
    Slice,
    IndexExpr,
    KnownIndex,
    UnknownIndex,
    IndexAnalysis,
    python_slice,
)

LOOP = Iter(py.Constant(0), range(3))
"""`LOOP` is the variable `i` of a loop that iterates over `range(3)`."""

N = ir.TestValue()
"""`N` is an integer parameter `n` whose range is unknown."""

i, n = IndexExpr.of(LOOP), IndexExpr.of(N)


def test_arithmetic_normalizes():
    assert (i + 1) - i == IndexExpr(1)
    assert i.scale(2) - i - i == IndexExpr(0)
    assert (i + n).substitute({N: IndexExpr(4)}) == i + 4


def test_constant_slices_match_python():
    for size in range(6):
        for a in (None, -7, -2, 0, 1, 3, 9):
            for b in (None, -7, -1, 0, 2, 4, 9):
                for step in (-3, -1, 1, 2):
                    start = None if a is None else IndexExpr(a)
                    stop = None if b is None else IndexExpr(b)
                    got = python_slice(start, stop, step, size)
                    assert got is not None and got.length is not None
                    items = [
                        got.item(IndexExpr(j)).offset for j in range(got.length.offset)
                    ]
                    assert items == list(range(size))[a:b:step], (size, a, b, step)


def test_symbolic_slices():
    pair = python_slice(i, i + 2, 1, 4)
    assert pair == Slice(i, 1, IndexExpr(2))
    assert pair.item(IndexExpr(1)) == i + 1
    assert python_slice(n, None, 1, 4) is None
    assert python_slice(IndexExpr(1), None, 2, None) == Slice(IndexExpr(1), 2, None)


def test_a_slice_of_a_slice_reads_the_register():
    outer = Slice(IndexExpr(2), 1, IndexExpr(4))
    inner = python_slice(IndexExpr(1), None, 1, 4)
    assert inner is not None
    assert outer.then(inner).item(IndexExpr(0)) == IndexExpr(3)


def test_a_stop_without_a_size_gives_no_slice():
    # Python clamps the stop to the size, so `x[1:3]` can hold 0, 1 or 2 items.
    assert python_slice(IndexExpr(1), IndexExpr(3), 1, None) is None
    assert python_slice(IndexExpr(1), None, 1, None) == Slice(IndexExpr(1), 1, None)


def test_a_slice_to_the_end_of_a_slice_keeps_the_outer_length():
    # `j` runs over `range(1, 3)`, so `j - 1` is never negative.
    j = IndexExpr.of(Iter(py.Constant(1), range(1, 3)))
    outer = Slice(IndexExpr(0), 1, j)
    assert outer.then(Slice(IndexExpr(1), 1, None)) == Slice(IndexExpr(1), 1, j - 1)
    # `i` can be 0, and then `i - 1` is negative.
    assert Slice(IndexExpr(0), 1, i).then(Slice(IndexExpr(1), 1, None)) is None
    assert Slice(IndexExpr(2), 1, IndexExpr(5)).then(
        Slice(IndexExpr(1), 2, None)
    ) == Slice(IndexExpr(3), 2, IndexExpr(2))
    assert outer.then(Slice(IndexExpr(1), 2, None)) is None


@squin.kernel
def odd_slot(n: int):
    qs = squin.qalloc(4)
    k = 2 * n - 1
    squin.x(qs[k])


def test_the_analysis_runs_on_a_kernel_with_symbolic_parameters():
    frame, _ = IndexAnalysis(odd_slot.dialects).run(odd_slot)
    n = odd_slot.callable_region.blocks[0].args[1]
    facts = {value.name: fact for value, fact in frame.entries.items() if value.name}
    assert facts["k"] == KnownIndex(IndexExpr.of(n).scale(2) - 1)
    assert facts["qs"] == UnknownIndex()
