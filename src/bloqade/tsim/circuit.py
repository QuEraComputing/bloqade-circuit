from kirin import ir

from bloqade.stim.circuit import _codegen

try:
    import tsim

    _Circuit = tsim.Circuit
except ImportError as _tsim_import_error:
    _TSIM_IMPORT_ERROR = _tsim_import_error

    class _MissingTsimCircuit:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "tsim is required for bloqade.tsim.Circuit. "
                'Install with: pip install "bloqade-circuit[tsim]". '
                f"Tsim import error: {_TSIM_IMPORT_ERROR}"
            ) from _TSIM_IMPORT_ERROR

    _Circuit = _MissingTsimCircuit


class Circuit(_Circuit):
    """A `tsim.Circuit` that can be built from a squin kernel or a program string."""

    def __init__(
        self, kernel: ir.Method | str, *args, insert_ticks: bool = False, **kwargs
    ):
        """Initialize tsim.Circuit from a kernel or a STIM program string.

        This class inherits from `tsim.Circuit`. For the full API reference of
        the underlying circuit class, see:
        https://queracomputing.github.io/tsim/latest/reference/tsim/circuit/

        Args:
            kernel: The kernel to compile into a tsim.Circuit, or a STIM program
                string to pass directly to the underlying circuit.
            *args: Additional positional arguments forwarded to `tsim.Circuit`.
            insert_ticks: When compiling a kernel, insert a ``TICK`` after every
                gate, reset, measurement, and noise operation so the diagram
                preserves the authored execution-order layering. Ignored when
                ``kernel`` is a program string.
            **kwargs: Additional keyword arguments forwarded to `tsim.Circuit`.

        """
        if isinstance(kernel, ir.Method):
            kernel = _codegen(kernel, insert_ticks=insert_ticks)
        super().__init__(kernel, *args, **kwargs)
