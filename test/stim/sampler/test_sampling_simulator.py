"""Tests for the stim/tsim sampling simulators."""

import numpy as np
import pytest

from bloqade import squin
from bloqade.tsim import SamplingSimulator as TsimSamplingSimulator
from bloqade.stim.sampler import SamplingSimulator as StimSamplingSimulator


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
        sim = simulator_cls()
        task = sim.task(kernel, sample_detectors=False)
        samples = task.run(shots=10)
        assert samples.shape == (10, 2)
        assert np.all(samples[:, 0] == samples[:, 1])

    def test_detector_sampling(self, simulator_cls):
        sim = simulator_cls()
        task = sim.task(kernel, sample_detectors=True)
        samples = task.run(shots=10)
        assert samples.shape == (10, 1)
        assert np.all(samples == samples[0, 0])

    def test_prepend_observables(self, simulator_cls):
        sim = simulator_cls()
        task = sim.task(kernel, sample_detectors=True)
        samples = task.run(shots=10, prepend_observables=True)
        assert samples.shape == (10, 2)
        assert np.all(samples[:, 1] == samples[0, 1])

    def test_append_observables(self, simulator_cls):
        sim = simulator_cls()
        task = sim.task(kernel, sample_detectors=True)
        samples = task.run(shots=10, append_observables=True)
        assert samples.shape == (10, 2)
        assert np.all(samples[:, 0] == samples[0, 0])

    def test_separate_observables(self, simulator_cls):
        sim = simulator_cls()
        task = sim.task(kernel, sample_detectors=True)
        det_samples, obs_samples = task.run(shots=10, separate_observables=True)
        assert det_samples.shape == (10, 1)
        assert obs_samples.shape == (10, 1)
        assert np.all(det_samples == det_samples[0, 0])

    def test_seed(self, simulator_cls):
        sim = simulator_cls()
        task1 = sim.task(kernel, sample_detectors=False, seed=42)
        task2 = sim.task(kernel, sample_detectors=False, seed=42)
        np.testing.assert_array_equal(task1.run(shots=10), task2.run(shots=10))
