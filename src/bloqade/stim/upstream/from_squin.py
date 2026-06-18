from kirin import ir

from ..groups import main
from ..passes.squin_to_stim import SquinToStimPass


def squin_to_stim(mt: ir.Method, insert_ticks: bool = False) -> ir.Method:
    new_mt = mt.similar()
    SquinToStimPass(mt.dialects, no_raise=False, insert_ticks=insert_ticks)(new_mt)
    return new_mt.similar(dialects=main)
