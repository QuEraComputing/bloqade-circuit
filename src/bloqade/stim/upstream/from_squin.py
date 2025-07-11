from kirin import ir

from ..groups import main
from ..passes.squin_to_stim import SquinToStimPass


def squin_to_stim(mt: ir.Method) -> ir.Method:
    new_mt = mt.similar()
    SquinToStimPass(mt.dialects, no_raise=False)(new_mt)
    return new_mt.similar(dialects=main)
