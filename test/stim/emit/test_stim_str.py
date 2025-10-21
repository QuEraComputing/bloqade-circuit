import pytest

from bloqade import stim
from bloqade.stim.emit import EmitStimMain


@pytest.mark.parametrize("debug", [True, False])
def test_debug_emit_with_source_info(debug: bool):
    @stim.main
    def test():
        stim.cx((0, 1), (2, 3))

    emit = EmitStimMain(debug=debug)
    emit.initialize()
    emit.run(mt=test, args=())
    output = emit.get_output()

    if debug:
        assert "# v--" in output
        assert ".py:" in output
    else:
        assert "# v--" not in output
