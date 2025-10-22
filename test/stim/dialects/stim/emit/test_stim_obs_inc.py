import io

from bloqade import stim
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.dialects import auxiliary


def test_obs_inc():

    @stim.main
    def test_simple_obs_inc():
        auxiliary.ObservableInclude(
            idx=3, targets=(auxiliary.GetRecord(-3), auxiliary.GetRecord(-1))
        )

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_simple_obs_inc)
    assert buf.getvalue().strip() == "OBSERVABLE_INCLUDE(3) rec[-3] rec[-1]"
