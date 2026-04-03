"""Utility for checking if an scf.For is eligible for REPEAT conversion."""

from kirin.analysis import const
from kirin.dialects.scf.stmts import For


def get_repeat_range(node: For) -> range | None:
    """Extract the range from a REPEAT-eligible scf.For, or None if not eligible.

    Eligible means:
    - iterable has a const.Value hint containing a range (possibly wrapped in IList)
    - loop variable (first block arg) has no uses
    """
    hint = node.iterable.hints.get("const")
    if not isinstance(hint, const.Value):
        return None

    # The hint data may be a plain range or an IList wrapping a range
    data = hint.data
    if isinstance(data, range):
        r = data
    elif hasattr(data, "data") and isinstance(data.data, range):
        # IList(range(...)) case
        r = data.data
    else:
        return None

    body_block = node.body.blocks[0]
    loop_var = body_block.args[0]
    if len(loop_var.uses) > 0:
        return None

    return r
