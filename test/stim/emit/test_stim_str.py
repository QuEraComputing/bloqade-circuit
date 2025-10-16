import pytest

from bloqade import squin
from bloqade.squin import qubit, kernel
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStimPass


@pytest.mark.parametrize("debug", [True, False])
def test_debug_emit_with_source_info(debug: bool):
    @kernel
    def test():
        q = qubit.new(2)
        squin.cx(q[0], q[1])

    SquinToStimPass(test.dialects)(test)

    emit = EmitStimMain(debug=debug)
    emit.initialize()
    emit.run(mt=test, args=())
    output = emit.get_output()

    if debug:
        assert "# v--" in output
    else:
        assert "# v--" not in output
