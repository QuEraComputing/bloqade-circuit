import io

from bloqade import stim
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.dialects import gate, auxiliary


def test_cx():

    @stim.main
    def test_simple_cx():
        gate.CX(controls=(4, 5, 6, 7), targets=(0, 1, 2, 3), dagger=False)

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_simple_cx)
    assert buf.getvalue().strip() == "CX 4 0 5 1 6 2 7 3"


def test_cx_cond_on_measure():

    @stim.main
    def test_simple_cx_cond_measure():
        gate.CX(
            controls=(auxiliary.GetRecord(id=-1), 4, auxiliary.GetRecord(id=-2)),
            targets=(0, 1, 2),
            dagger=False,
        )

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_simple_cx_cond_measure)
    assert buf.getvalue().strip() == "CX rec[-1] 0 4 1 rec[-2] 2"
