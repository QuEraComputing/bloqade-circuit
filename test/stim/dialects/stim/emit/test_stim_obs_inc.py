from bloqade import stim
from bloqade.stim.dialects import auxiliary

from .base import codegen


def test_obs_inc():

    @stim.main
    def test_simple_obs_inc():
        auxiliary.ObservableInclude(
            idx=3, targets=(auxiliary.GetRecord(-3), auxiliary.GetRecord(-1))
        )

    out = codegen(test_simple_obs_inc)

    assert out.strip() == "OBSERVABLE_INCLUDE(3) rec[-3] rec[-1]"
