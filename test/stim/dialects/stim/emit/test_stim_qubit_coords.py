import io
from bloqade import stim
from bloqade.stim.dialects import auxiliary
from bloqade.stim.emit import EmitStimMain


def test_qcoords():

    @stim.main
    def test_simple_qcoords():
        auxiliary.QubitCoordinates(coord=(0.1, 0.2), target=3)

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_simple_qcoords)
    assert buf.getvalue().strip() == "QUBIT_COORDS(0.10000000, 0.20000000) 3"
