"""Sampling of low-magic universal quantum circuits using tsim.

Example:
    Sample measurements from a Bell state circuit::

        ```python
        from bloqade import squin
        from bloqade.tsim import SamplingSimulator

        @squin.kernel
        def bell_state():
            q = squin.qalloc(2)
            squin.h(q[0])
            squin.cx(q[0], q[1])
            squin.broadcast.measure(q)

        sampler = SamplingSimulator(bell_state)
        samples = sampler.sample(shots=1_000_000, batch_size=100_000)
        ```

    Sample detectors for error correction::

        ```python
        from bloqade.tsim import DetectorSamplingSimulator

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
            shots=1_000_000, batch_size=100_000, separate_observables=True
        )
        ```

Note:
    Increasing ``batch_size`` can significantly improve performance. When using a GPU
    it is recommended to increase it until VRAM is fully utilized.
"""

from kirin import ir

from bloqade.stim.sampler.sampler import _codegen

try:
    import tsim

    _MeasurementSamplerBase = tsim.CompiledMeasurementSampler
    _DetectorSamplerBase = tsim.CompiledDetectorSampler
except ImportError:

    class _MissingTsim:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "tsim is required for GPU-accelerated sampling. "
                'Install with: pip install "bloqade-circuit[tsim]"'
            )

    _MeasurementSamplerBase = _MissingTsim
    _DetectorSamplerBase = _MissingTsim
    tsim = None


class SamplingSimulator(_MeasurementSamplerBase):
    """Sampling of low-magic universal quantum circuits using tsim.

    Args:
        kernel: The squin kernel to compile and sample from.

    Example::

        ```python
        sampler = SamplingSimulator(my_kernel)
        samples = sampler.sample(shots=1_000_000, batch_size=100_000)
        ```

    Note:
        Increasing ``batch_size`` can significantly improve performance.
        When using a GPU it is recommended to increase it until VRAM is fully utilized.
    """

    def __init__(self, kernel: ir.Method):
        program_text = _codegen(kernel)
        circuit = tsim.Circuit(program_text)
        super().__init__(circuit)


class DetectorSamplingSimulator(_DetectorSamplerBase):
    """Sampling of low-magic universal quantum circuits using tsim.

    Args:
        kernel: The squin kernel to compile and sample from.
            Must contain `squin.annotate.set_detector` annotations.

    Example::

        ```python
        sampler = DetectorSamplingSimulator(my_kernel)
        det_samples, obs_samples = sampler.sample(
            shots=1_000_000, batch_size=100_000, separate_observables=True
        )
        ```
    Note:
        Increasing ``batch_size`` can significantly improve performance.
        When using a GPU it is recommended to increase it until VRAM is fully utilized.
    """

    def __init__(self, kernel: ir.Method):
        program_text = _codegen(kernel)
        self.circuit = tsim.Circuit(program_text)
        super().__init__(self.circuit)
