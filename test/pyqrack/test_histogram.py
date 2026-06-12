import numpy as np

from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator


def test_histogram_bell():
    """A Bell state has two equally weighted basis states."""

    @squin.kernel
    def bell():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])
        return q

    emulator = StackMemorySimulator(min_qubits=2)
    hist = emulator.task(bell).histogram()

    assert set(hist) == {"00", "11"}
    assert np.isclose(hist["00"], 0.5)
    assert np.isclose(hist["11"], 0.5)


def test_histogram_basis_state():
    """A single X gate gives one basis state with probability 1.

    This also validates the bit ordering: applying X to the first qubit must
    flip the FIRST bit, consistent with Cirq (see quantum_state).
    """

    @squin.kernel
    def flip_first():
        q = squin.qalloc(2)
        squin.x(q[0])
        return q

    emulator = StackMemorySimulator(min_qubits=2)
    hist = emulator.task(flip_first).histogram()

    assert set(hist) == {"10"}
    assert np.isclose(hist["10"], 1.0)


def test_histogram_ghz():
    """A 3-qubit GHZ state splits weight between all-zeros and all-ones."""

    @squin.kernel
    def ghz():
        q = squin.qalloc(3)
        squin.h(q[0])
        squin.cx(q[0], q[1])
        squin.cx(q[1], q[2])
        return q

    emulator = StackMemorySimulator(min_qubits=3)
    hist = emulator.task(ghz).histogram()

    assert set(hist) == {"000", "111"}
    assert np.isclose(hist["000"], 0.5)
    assert np.isclose(hist["111"], 0.5)


def test_histogram_shots_counts():
    """With shots, the histogram returns integer counts summing to shots."""

    @squin.kernel
    def bell():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])
        return q

    emulator = StackMemorySimulator(min_qubits=2)
    shots = 2000
    hist = emulator.task(bell).histogram(shots=shots)

    assert set(hist).issubset({"00", "11"})
    assert all(isinstance(count, int) for count in hist.values())
    assert sum(hist.values()) == shots
    # Bell is ~50/50; loose bounds keep this effectively deterministic.
    assert 0.4 * shots < hist["00"] < 0.6 * shots
    assert 0.4 * shots < hist["11"] < 0.6 * shots
