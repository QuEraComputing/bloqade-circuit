import io
from bloqade import stim
from bloqade.stim.emit import EmitStimMain



def test_detector():

    @stim.main
    def test_simple_cx():
        stim.detector(coord=(1, 2, 3), targets=(stim.rec(-3), stim.rec(-1)))

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_simple_cx)
    assert buf.getvalue().strip() == "DETECTOR(1, 2, 3) rec[-3] rec[-1]"
