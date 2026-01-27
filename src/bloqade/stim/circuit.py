import io

from kirin import ir

from bloqade.stim import groups as bloqade_stim
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStimPass

try:
    import stim

    _Circuit = stim.Circuit
except ImportError:

    class _MissingStimCircuit:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "stim is required for bloqade.stim.Circuit. "
                'Install with: pip install "bloqade-circuit[stim]"'
            )

    _Circuit = _MissingStimCircuit
    stim = None


def _codegen(mt: ir.Method) -> str:
    """Compile a kernel to STIM program string."""
    mt = mt.similar()
    SquinToStimPass(mt.dialects)(mt)
    buf = io.StringIO()
    emit = EmitStimMain(dialects=bloqade_stim.main, io=buf)
    emit.initialize()
    emit.run(mt)
    return buf.getvalue().strip()


class Circuit(_Circuit):
    def __init__(self, kernel: ir.Method):
        program_text = _codegen(kernel)
        super().__init__(program_text)
