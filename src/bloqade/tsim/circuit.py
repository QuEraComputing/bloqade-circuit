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
    """A `tsim.Circuit` that can be built from a squin kernel or a program string."""

    def __init__(self, kernel: ir.Method | str, *args, **kwargs):
        """Initialize tsim.Circuit from a kernel or a STIM program string.

        This class inherits from `tsim.Circuit`. For the full API reference of
        the underlying circuit class, see:
        https://queracomputing.github.io/tsim/latest/reference/tsim/circuit/

        Args:
            kernel: The kernel to compile into a tsim.Circuit, or a STIM program
                string to pass directly to the underlying circuit.
            *args: Additional positional arguments forwarded to `tsim.Circuit`.
            **kwargs: Additional keyword arguments forwarded to `tsim.Circuit`.

        """
        if isinstance(kernel, ir.Method):
            kernel = _codegen(kernel)
        super().__init__(kernel, *args, **kwargs)
