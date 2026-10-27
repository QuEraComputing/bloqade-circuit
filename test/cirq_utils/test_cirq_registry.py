import pytest
from kirin import ir

from bloqade.cirq_registry import resolve_cirq_loader, register_cirq_loader


def test_resolve_registered_loader():
    dialect = ir.Dialect("test_cirq_loader_dispatch")
    dialects = ir.DialectGroup([dialect])
    calls: list[bool] = []

    def factory():
        calls.append(True)
        return object

    register_cirq_loader(dialects, factory)
    register_cirq_loader(dialects, factory)

    assert not calls
    assert resolve_cirq_loader(ir.DialectGroup([dialect])) is object
    assert calls == [True]
    assert resolve_cirq_loader(ir.DialectGroup([])) is None

    with pytest.raises(ValueError, match="already registered"):
        register_cirq_loader(dialects, lambda: object)


def test_loader_only_matches_complete_dialect_group():
    first = ir.Dialect("test_cirq_loader_first")
    second = ir.Dialect("test_cirq_loader_second")
    dialects = ir.DialectGroup([first, second])
    register_cirq_loader(dialects, lambda: object)

    assert resolve_cirq_loader(dialects) is object
    assert resolve_cirq_loader(ir.DialectGroup([first])) is None
    assert resolve_cirq_loader(ir.DialectGroup([second])) is None
