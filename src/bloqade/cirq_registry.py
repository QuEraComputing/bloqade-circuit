"""Lightweight registration for dialect-specific Cirq conversions.

This module deliberately does not import Cirq: dialect groups can register an
integration without making Cirq a mandatory dependency of their package.
"""

from typing import Any
from collections.abc import Callable

from kirin import ir

_loaders: dict[frozenset[ir.Dialect], Callable[[], type[Any]]] = {}


def register_cirq_loader(
    dialects: ir.DialectGroup, factory: Callable[[], type[Any]]
) -> None:
    """Register a lazy Cirq lowerer for a dialect group."""
    key = dialects.data
    existing = _loaders.get(key)
    if existing is not None and existing is not factory:
        raise ValueError(f"A Cirq loader is already registered for {dialects!r}")
    _loaders[key] = factory


def resolve_cirq_loader(dialects: ir.DialectGroup) -> type[Any] | None:
    """Load the integration registered for this exact dialect group, if any."""
    factory = _loaders.get(dialects.data)
    if factory is None:
        return None
    return factory()
