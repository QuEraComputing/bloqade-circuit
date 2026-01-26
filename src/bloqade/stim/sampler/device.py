from dataclasses import dataclass

import stim
from bloqade.stim.sampler.base import SamplingSimulatorBase
from bloqade.stim.sampler.task import SamplingTask


@dataclass
class SamplingSimulator(SamplingSimulatorBase[SamplingTask]):
    """Stabilizer circuit sampling simulator using STIM.

    This simulator compiles squin kernels to STIM format and uses STIM for sampling.
    It supports both measurement sampling and detector sampling.

    Example:
        Sample measurements:
            sim = SamplingSimulator()
            task = sim.task(circuit, sample_detectors=False)
            samples = task.run(shots=1000)

        Sample detectors with observables::

            @squin.kernel
            def circuit_with_detectors():
                q = squin.qalloc(2)
                squin.h(q[0])
                squin.cx(q[0], q[1])
                measurements = squin.broadcast.measure(q)
                squin.annotate.set_detector(measurements, coordinates=[0, 0])
                squin.annotate.set_observable([measurements[0]], idx=0)

            sim = SamplingSimulator()
            task = sim.task(circuit_with_detectors, sample_detectors=True)
            det_samples, obs_samples = task.run(shots=1000, separate_observables=True)
    """

    def __post_init__(self):
        self._backend = stim
        self._task_class = SamplingTask
