"""Lightweight registration for dialect-specific Cirq conversions.

This module deliberately does not import Cirq: dialect groups can register an
integration without making Cirq a mandatory dependency of their package.
"""

from typing import Any
from collections.abc import Callable

from kirin import ir

_loaders: dict[str, Callable[[], type[Any]]] = {}


def register_cirq_loader(dialect: ir.Dialect, factory: Callable[[], type[Any]]) -> None:
    """Register a lazy Cirq lowerer for a distinctive dialect."""
    existing = _loaders.get(dialect.name)
    if existing is not None and existing is not factory:
        raise ValueError(f"A Cirq loader is already registered for {dialect.name!r}")
    _loaders[dialect.name] = factory


def resolve_cirq_loader(dialects: ir.DialectGroup) -> type[Any] | None:
    """Load the sole matching integration, if the group has one."""
    matches = [(d.name, _loaders[d.name]) for d in dialects if d.name in _loaders]
    if len(matches) > 1:
        names = ", ".join(sorted(name for name, _ in matches))
        raise ValueError(f"Multiple Cirq loaders match this dialect group: {names}")
    if not matches:
        return None
    return matches[0][1]()
