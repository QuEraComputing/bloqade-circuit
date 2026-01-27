import numpy as np
import pytest

from bloqade import squin
from bloqade.stim.sampler.sampler import (
    SamplingSimulator as StimSamplingSimulator,
    DetectorSamplingSimulator as StimDetectorSamplingSimulator,
)
from bloqade.tsim.sampler.sampler import (
    SamplingSimulator as TsimSamplingSimulator,
    DetectorSamplingSimulator as TsimDetectorSamplingSimulator,
)


@squin.kernel
def kernel():
    q = squin.qalloc(2)
    squin.h(q[0])
    squin.cx(q[0], q[1])
    measurements = squin.broadcast.measure(q)
    squin.annotate.set_detector(measurements, coordinates=[0, 0])
    squin.annotate.set_observable([measurements[0]], idx=0)


@pytest.mark.parametrize(
    "simulator_cls",
    [StimSamplingSimulator, TsimSamplingSimulator],
    ids=["stim", "tsim"],
)
class TestSamplingSimulator:

    def test_measurement_sampling(self, simulator_cls):
        sampler = simulator_cls(kernel)
        samples = sampler.sample(shots=10)
        assert samples.shape == (10, 2)
        assert np.all(samples[:, 0] == samples[:, 1])


@pytest.mark.parametrize(
    "simulator_cls",
    [StimDetectorSamplingSimulator, TsimDetectorSamplingSimulator],
    ids=["stim", "tsim"],
)
class TestDetectorSamplingSimulator:

    def test_detector_sampling(self, simulator_cls):
        sampler = simulator_cls(kernel)
        samples = sampler.sample(shots=10)
        assert samples.shape == (10, 1)
        assert np.all(samples == samples[0, 0])

    def test_prepend_observables(self, simulator_cls):
        sampler = simulator_cls(kernel)
        samples = sampler.sample(shots=10, prepend_observables=True)
        assert samples.shape == (10, 2)
        assert np.all(samples[:, 1] == samples[0, 1])

    def test_append_observables(self, simulator_cls):
        sampler = simulator_cls(kernel)
        samples = sampler.sample(shots=10, append_observables=True)
        assert samples.shape == (10, 2)
        assert np.all(samples[:, 0] == samples[0, 0])

    def test_separate_observables(self, simulator_cls):
        sampler = simulator_cls(kernel)
        det_samples, obs_samples = sampler.sample(shots=10, separate_observables=True)
        assert det_samples.shape == (10, 1)
        assert obs_samples.shape == (10, 1)
        assert np.all(det_samples == det_samples[0, 0])
