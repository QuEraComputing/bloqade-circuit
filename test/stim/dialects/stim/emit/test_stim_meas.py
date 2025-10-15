import io
from bloqade import stim
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.dialects import collapse

def test_meas():

    @stim.main
    def test_simple_meas():
        collapse.MX(p=0.3, targets=(0, 3, 4, 5))

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_simple_meas)
    assert buf.getvalue().strip() == "MX(0.30000000) 0 3 4 5"
