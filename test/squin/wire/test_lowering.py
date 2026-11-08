"""Check direct Python lowering and the existing wire validation rules."""

import pytest
from kirin import lowering
from kirin.dialects import func
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.pyqrack import DynamicMemorySimulator
from bloqade.squin.wire.lowering import wire_kernel
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin


@wire_kernel
def bell_pairs(n: int):
    qs = squin.qalloc(2 * n)
    for i in range(n):
        squin.h(qs[2 * i])
        squin.cx(qs[2 * i], qs[2 * i + 1])
    return squin.broadcast.measure(qs)


@pytest.mark.parametrize("n", [0, 1, 3])
def test_bell_pairs_stay_correlated(n):
    restored = WireToSquin().emit(bell_pairs)
    for _ in range(8):
        bits = list(DynamicMemorySimulator().run(restored, args=(n,)))
        assert len(bits) == 2 * n
        assert all(bits[i] == bits[i + 1] for i in range(0, len(bits), 2))


def test_direct_lowering_needs_no_reference_conversion(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Direct lowering must build wire operations itself.")

    monkeypatch.setattr(SquinToWire, "emit", forbidden)

    @wire_kernel
    def flipped(n: int):
        qs = squin.qalloc(n)
        for i in range(n):
            squin.x(qs[i])
        return squin.broadcast.measure(qs)

    assert not any(isinstance(node, func.Invoke) for node in flipped.code.walk())
    restored = WireToSquin().emit(flipped)
    assert list(DynamicMemorySimulator().run(restored, args=(3,))) == [1, 1, 1]


def test_unknown_overlap_fails_during_decoration():
    with pytest.raises(ValidationErrorGroup, match="Cannot prove"):

        @wire_kernel
        def uncertain(i: int, j: int):
            qs = squin.qalloc(3)
            squin.cx(qs[i], qs[j])


def test_known_overlap_fails_during_decoration():
    with pytest.raises(ValidationErrorGroup, match="already out of its register"):

        @wire_kernel
        def duplicate(i: int):
            qs = squin.qalloc(3)
            squin.cx(qs[i], qs[i])


def test_register_aliases_share_updated_wire_state():
    @wire_kernel
    def alias():
        qs = squin.qalloc(3)
        other = qs
        q = other[0]
        squin.x(q)
        squin.x(qs[0])
        return squin.broadcast.measure(other)

    restored = WireToSquin().emit(alias)
    assert list(DynamicMemorySimulator().run(restored)) == [0, 0, 0]


def test_kirin_resolves_imported_callable_names():
    allocate = squin.qalloc
    flip = squin.x
    measure = squin.broadcast.measure

    @wire_kernel
    def renamed(n: int):
        qs = allocate(n)
        for i in range(n):
            flip(qs[i])
        return measure(qs)

    restored = WireToSquin().emit(renamed)
    assert list(DynamicMemorySimulator().run(restored, args=(3,))) == [1, 1, 1]


def test_kirin_carries_registers_through_nested_loops():
    @wire_kernel
    def nested(n: int):
        qs = squin.qalloc(3)
        for i in range(n):
            for j in range(3):
                squin.x(qs[j])
        return squin.broadcast.measure(qs)

    restored = WireToSquin().emit(nested)
    for n in (0, 1, 2):
        assert list(DynamicMemorySimulator().run(restored, args=(n,))) == [n % 2] * 3


def test_lowering_errors_keep_the_python_source_location():
    with pytest.raises(lowering.BuildError) as caught:

        @wire_kernel
        def branch(n: int):
            qs = squin.qalloc(1)
            return qs

    assert caught.value.source.file == __file__
    assert caught.value.lines[caught.value.source.lineno - 1].strip() == "return qs"
