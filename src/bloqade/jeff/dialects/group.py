"""This module holds the dialect groups for jeff programs."""

from kirin import ir
from kirin.dialects import func, ssacfg

from .stmts import scf, call, gate, wire, classical

function = ir.DialectGroup([call.dialect, func])
"""The smallest dialect group that a callable jeff function needs.

The group holds jeff's call and return statements and kirin's `func` dialect.
"""

kernel = ir.DialectGroup(
    [
        call.dialect,
        func,
        classical.dialect,
        wire.dialect,
        gate.dialect,
        scf.dialect,
        ssacfg,
    ]
)
"""The dialect group for pure jeff programs.

The group holds every jeff dialect, kirin's `func` dialect and kirin's `ssacfg` dialect.
"""
