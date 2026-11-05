"""Check wire validation during squin kernel decoration."""

import pytest
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.pyqrack import DynamicMemorySimulator
from bloqade.squin.wire.group import is_wire


@pytest.mark.parametrize("fold", [False, True])
@pytest.mark.parametrize("typeinfer", [False, True])
def test_wirevalidation_preserves_a_runnable_source_kernel(fold, typeinfer):
    @squin.kernel(wirevalidation=True, fold=fold, typeinfer=typeinfer)
    def checked():
        qs = squin.qalloc(2)
        squin.x(qs[0])
        squin.cx(qs[0], qs[1])
        return squin.broadcast.measure(qs)

    assert checked.dialects is squin.kernel
    assert not is_wire(checked)
    assert list(DynamicMemorySimulator().run(checked)) == [1, 1]


@pytest.mark.parametrize("wirevalidation", [False, True])
def test_wirevalidation_rejects_uncertain_borrows_when_enabled(wirevalidation):
    def compile_kernel():
        @squin.kernel(wirevalidation=wirevalidation)
        def checked(i: int, j: int):
            qs = squin.qalloc(3)
            squin.cx(qs[i], qs[j])

        return checked

    if wirevalidation:
        with pytest.raises(ValidationErrorGroup, match="Cannot prove"):
            compile_kernel()
    else:
        compile_kernel()


def test_wirevalidation_rejects_a_known_double_borrow_during_decoration():
    with pytest.raises(ValidationErrorGroup, match="already out of its register"):

        @squin.kernel(wirevalidation=True)
        def checked():
            qs = squin.qalloc(1)
            squin.cx(qs[0], qs[0])


def test_wirevalidation_accepts_adjacent_borrows_in_a_loop():
    @squin.kernel(wirevalidation=True)
    def checked(n: int):
        qs = squin.qalloc(2 * n)
        for i in range(n):
            squin.cx(qs[2 * i], qs[2 * i + 1])

    assert checked.dialects is squin.kernel


def test_wirevalidation_checks_callees():
    @squin.kernel
    def unchecked(i: int, j: int):
        qs = squin.qalloc(3)
        squin.cx(qs[i], qs[j])

    before = unchecked.code.print_str()
    with pytest.raises(ValidationErrorGroup, match="Cannot prove"):

        @squin.kernel(wirevalidation=True)
        def checked(i: int, j: int):
            unchecked(i, j)

    assert unchecked.code.print_str() == before


def test_wirevalidation_defaults_to_false():
    @squin.kernel
    def unchecked(i: int, j: int):
        qs = squin.qalloc(3)
        squin.cx(qs[i], qs[j])

    assert unchecked.dialects is squin.kernel
