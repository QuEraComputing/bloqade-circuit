"""STIM-based stabilizer circuit sampling simulators.

Example:
    Sample measurements from a Bell state circuit::

        ```python
        from bloqade import squin
        from bloqade.stim.sampler import SamplingSimulator

        @squin.kernel
        def bell_state():
            q = squin.qalloc(2)
            squin.h(q[0])
            squin.cx(q[0], q[1])
            squin.broadcast.measure(q)

        sampler = SamplingSimulator(bell_state)
        samples = sampler.sample(shots=1000)
        ```
    Sample detectors for error correction::

        ```python
        from bloqade.stim.sampler import DetectorSamplingSimulator

        @squin.kernel
        def bell_with_detector():
            q = squin.qalloc(2)
            squin.h(q[0])
            squin.cx(q[0], q[1])
            measurements = squin.broadcast.measure(q)
            squin.annotate.set_detector(measurements, coordinates=[0, 0])
            squin.annotate.set_observable([measurements[0]], idx=0)

        sampler = DetectorSamplingSimulator(bell_with_detector)
        det_samples, obs_samples = sampler.sample(
            shots=1000, separate_observables=True
        )
        ```
"""

import io

from kirin import ir

from bloqade.stim import groups as bloqade_stim
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStimPass

try:
    import stim

    _MeasurementSamplerBase = stim.CompiledMeasurementSampler
    _DetectorSamplerBase = stim.CompiledDetectorSampler
except ImportError:

    class _MissingStim:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "stim is required for SamplingSimulator. "
                'Install with: pip install "bloqade-circuit[stim]"'
            )

    _MeasurementSamplerBase = _MissingStim
    _DetectorSamplerBase = _MissingStim
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


class SamplingSimulator(_MeasurementSamplerBase):
    """Stabilizer circuit measurement sampler using stim.

    Args:
        kernel: The squin kernel to compile and sample from.

    Example::

        ```python
        sampler = SamplingSimulator(my_kernel)
        samples = sampler.sample(shots=1000)
        ```
    """

    def __init__(self, kernel: ir.Method):
        program_text = _codegen(kernel)
        circuit = stim.Circuit(program_text)
        super().__init__(circuit)


class DetectorSamplingSimulator(_DetectorSamplerBase):
    """Stabilizer circuit detector sampler using stim.

    Args:
        kernel: The squin kernel to compile and sample from.
            Must contain DETECTOR annotations.

    Example::

        ```python
        sampler = DetectorSamplingSimulator(my_kernel)
        det_samples, obs_samples = sampler.sample(
            shots=1000, separate_observables=True
        )
        ```
    """

    def __init__(self, kernel: ir.Method):
        program_text = _codegen(kernel)
        self.circuit = stim.Circuit(program_text)
        super().__init__(self.circuit)
