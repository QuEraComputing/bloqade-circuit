import pytest
from kirin import ir

from bloqade.cirq_registry import resolve_cirq_loader, register_cirq_loader


def test_resolve_registered_loader():
    dialect = ir.Dialect("test_cirq_loader_dispatch")
    calls: list[bool] = []

    def factory():
        calls.append(True)
        return object

    register_cirq_loader(dialect, factory)
    register_cirq_loader(dialect, factory)

    assert not calls
    assert resolve_cirq_loader(ir.DialectGroup([dialect])) is object
    assert calls == [True]
    assert resolve_cirq_loader(ir.DialectGroup([])) is None

    with pytest.raises(ValueError, match="already registered"):
        register_cirq_loader(dialect, lambda: object)


def test_multiple_registered_loaders_are_ambiguous():
    first = ir.Dialect("test_cirq_loader_first")
    second = ir.Dialect("test_cirq_loader_second")
    register_cirq_loader(first, lambda: object)
    register_cirq_loader(second, lambda: object)

    with pytest.raises(ValueError, match="Multiple Cirq loaders"):
        resolve_cirq_loader(ir.DialectGroup([first, second]))
