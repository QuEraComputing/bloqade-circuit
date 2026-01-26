"""TSim sampling simulator device."""

from dataclasses import dataclass

import tsim
from bloqade.stim.sampler.base import SamplingSimulatorBase
from bloqade.tsim.sampler.task import SamplingTask


@dataclass
class SamplingSimulator(SamplingSimulatorBase[SamplingTask]):
    """Low magic universal quantum circuit sampling with TSIM.

    This simulator compiles squin kernels to extended STIM format and uses TSIM for
    sampling. It supports both measurement sampling and detector sampling, optionally
    with GPU acceleration.

    Example:
        Sample measurements with GPU batching::

            from bloqade import squin
            from bloqade.tsim import SamplingSimulator

            @squin.kernel
            def circuit():
                q = squin.qalloc(2)
                squin.h(q[0])
                squin.t(q[0])
                squin.cx(q[0], q[1])
                return squin.broadcast.measure(q)

            sim = SamplingSimulator()
            task = sim.task(circuit, sample_detectors=False)
            samples = task.run(shots=1_000_000, batch_size=100_000)

        Sample detectors with observables::

            @squin.kernel
            def circuit_with_detectors():
                q = squin.qalloc(2)
                squin.h(q[0])
                squin.t(q[0])
                squin.cx(q[0], q[1])
                measurements = squin.broadcast.measure(q)
                squin.annotate.set_detector(measurements, coordinates=[0, 0])
                squin.annotate.set_observable([measurements[0]], idx=0)

            sim = SamplingSimulator()
            task = sim.task(circuit_with_detectors, sample_detectors=True)
            det_samples, obs_samples = task.run(
                shots=1_000_000,
                batch_size=100_000,
                separate_observables=True,
            )

    Note:
        A large ``batch_size`` can significantly improve performance. On GPU, it is
        recommended to increase this value until VRAM is fully utilized.
    """

    def __post_init__(self):
        self._backend = tsim
        self._task_class = SamplingTask
