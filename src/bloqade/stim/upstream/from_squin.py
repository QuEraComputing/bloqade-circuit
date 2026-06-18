from kirin import ir

from ..groups import main
from ..passes.squin_to_stim import SquinToStimPass


def squin_to_stim(mt: ir.Method, insert_ticks: bool = False) -> ir.Method:
    """Lower a squin kernel to the STIM dialect.

    Args:
        mt: The squin kernel to lower.
        insert_ticks: If True, insert a ``TICK`` after every gate, reset,
            measurement, and noise operation so the emitted circuit preserves
            the authored execution-order layering when rendered as a diagram.
            Timing-only, so record/detector indexing is unaffected.

    Returns:
        A new method lowered to the STIM main dialect group.
    """
    new_mt = mt.similar()
    SquinToStimPass(mt.dialects, no_raise=False, insert_ticks=insert_ticks)(new_mt)
    return new_mt.similar(dialects=main)
