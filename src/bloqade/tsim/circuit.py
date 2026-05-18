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


class Circuit(_Circuit):
    def __init__(self, kernel: ir.Method):
        """Initialize tsim.Circuit from a kernel.

        This class inherits from `tsim.Circuit`. For the full API reference of
        the underlying circuit class, see:
        https://queracomputing.github.io/tsim/latest/reference/tsim/circuit/

        Args:
            kernel: The kernel to compile into a tsim.Circuit.

        """
        program_text = _codegen(kernel)
        super().__init__(program_text)
