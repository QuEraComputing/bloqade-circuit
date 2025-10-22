import io
from bloqade import stim
from bloqade.stim.emit import EmitStimMain


def test_x():

    @stim.main
    def test_x():
        stim.x(targets=(0, 1, 2, 3), dagger=False)

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_x)
    assert buf.getvalue().strip() == "X 0 1 2 3"

    @stim.main
    def test_x_dag():
        stim.x(targets=(0, 1, 2, 3), dagger=True)

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_x_dag)
    assert buf.getvalue().strip() == "X 0 1 2 3"


def test_y():

    @stim.main
    def test_y():
        stim.y(targets=(0, 1, 2, 3), dagger=False)

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_y)
    assert buf.getvalue().strip() == "Y 0 1 2 3"

    @stim.main
    def test_y_dag():
        stim.y(targets=(0, 1, 2, 3), dagger=True)

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_y_dag)
    assert buf.getvalue().strip() == "Y 0 1 2 3"
