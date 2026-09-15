"""Shared helpers for the jeff tests."""

import tempfile
from pathlib import Path

from bloqade.jeff import emit_jeff, load_jeff


def roundtrips(lowered) -> bool:
    """Check that emit, write, load, emit, write is byte-identical."""
    module = emit_jeff(lowered)
    with tempfile.TemporaryDirectory() as tmp:
        first, second = Path(tmp) / "a.jeff", Path(tmp) / "b.jeff"
        module.write_out(str(first))
        emit_jeff(load_jeff(str(first))).write_out(str(second))
        return first.read_bytes() == second.read_bytes()
