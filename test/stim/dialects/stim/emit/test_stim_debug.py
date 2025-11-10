import io

from kirin.dialects import debug

from bloqade import stim
from bloqade.stim.emit import EmitStimMain


def test_debug():

    @stim.main
    def test_debug_main():
        debug.info("debug message")

    test_debug_main.print()

    buf = io.StringIO()
    stim_emit: EmitStimMain[io.StringIO] = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_debug_main)
    assert buf.getvalue().strip() == "# debug message"
