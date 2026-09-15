"""Shared helpers for the jeff tests."""

import tempfile
from pathlib import Path

from bloqade.jeff import emit_jeff, load_jeff


def roundtrips(lowered) -> bool:
    """Check that a module keeps its text form through emit, write, load and emit.

    The text form names each string. The file bytes hold indices into the string
    table, and the order of that table depends on the hash seed.
    """
    first = emit_jeff(lowered)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "a.jeff"
        first.write_out(str(path))
        second = emit_jeff(load_jeff(str(path)))
    return str(first) == str(second)
