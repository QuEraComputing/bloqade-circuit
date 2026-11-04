"""Define `kernel`, the dialect group of wire squin methods.

The group holds the squin, native gate and wire dialects. A wire squin method
can therefore keep its classical statements unchanged. A source with statements of
other dialects gets the larger group of `wire_group`.
"""

from collections.abc import Iterable

from kirin import ir

from bloqade.squin.groups import kernel as squin_kernel
from bloqade.native.dialects import gate as native_gate

from ._dialect import dialect

reference_kernel = squin_kernel.union([native_gate])
kernel = reference_kernel.union([dialect])


def wire_group(
    source: ir.DialectGroup, wire_dialects: Iterable[ir.Dialect] = ()
) -> ir.DialectGroup:
    """Return the dialect group of the wire methods of the source group `source`.

    A source dialect outside `reference_kernel`, such as a Gemini dialect, joins the
    group. `wire_dialects` holds the dialects of the wire statements that such a
    dialect emits.
    """
    extra = (source.data - reference_kernel.data) | set(wire_dialects)
    return kernel.union(extra) if extra else kernel


def reference_group(
    wired: ir.DialectGroup, wire_dialects: Iterable[ir.Dialect] = ()
) -> ir.DialectGroup:
    """Return the dialect group of the squin kernels of the wire group `wired`."""
    extra = wired.data - kernel.data - set(wire_dialects)
    return reference_kernel.union(extra) if extra else reference_kernel


def is_wire(method: ir.Method) -> bool:
    """Check whether `method` is a wire method."""
    return dialect in method.dialects.data
