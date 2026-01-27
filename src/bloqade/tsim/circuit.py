from kirin import ir

from bloqade.stim.circuit import _codegen

try:
    import tsim

    _Circuit = tsim.Circuit
except ImportError:

    class _MissingTsimCircuit:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "tsim is required for bloqade.tsim.Circuit. "
                'Install with: pip install "bloqade-circuit[tsim]"'
            )

    _Circuit = _MissingTsimCircuit
    tsim = None


class Circuit(_Circuit):
    def __init__(self, kernel: ir.Method):
        program_text = _codegen(kernel)
        super().__init__(program_text)
