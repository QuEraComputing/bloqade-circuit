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


def _codegen(mt: ir.Method, insert_ticks: bool = False) -> str:
    """Compile a kernel to STIM program string.

    Args:
        mt: The kernel to compile.
        insert_ticks: If True, insert a ``TICK`` after every gate, reset,
            measurement, and noise operation so the emitted circuit preserves
            the authored execution-order layering when rendered as a diagram.
            Timing-only, so record/detector indexing is unaffected.
    """
    mt = mt.similar()
    SquinToStimPass(mt.dialects, insert_ticks=insert_ticks)(mt)
    buf = io.StringIO()
    emit = EmitStimMain(dialects=bloqade_stim.main, io=buf)
    emit.initialize()
    emit.run(mt)
    return buf.getvalue().strip()


class Circuit(_Circuit):
    """A `stim.Circuit` that can be built from a squin kernel or a program string."""

    def __init__(
        self, kernel: ir.Method | str, *args, insert_ticks: bool = False, **kwargs
    ):
        """Initialize stim.Circuit from a kernel or a STIM program string.

        This class inherits from `stim.Circuit`. For the full API reference of
        the underlying circuit class, see:
        https://github.com/quantumlib/Stim/blob/main/doc/python_api_reference_vDev.md#stim.Circuit

        Args:
            kernel: The kernel to compile into a stim.Circuit, or a STIM program
                string to pass directly to the underlying circuit.
            *args: Additional positional arguments forwarded to `stim.Circuit`.
            insert_ticks: When compiling a kernel, insert a ``TICK`` after every
                gate, reset, measurement, and noise operation so the diagram
                preserves the authored execution-order layering. Ignored when
                ``kernel`` is a program string.
            **kwargs: Additional keyword arguments forwarded to `stim.Circuit`.

        """
        if isinstance(kernel, ir.Method):
            kernel = _codegen(kernel, insert_ticks=insert_ticks)
        super().__init__(kernel, *args, **kwargs)
