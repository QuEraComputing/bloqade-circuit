import numpy as np
import pytest

from bloqade import squin
from bloqade.pyqrack import PyQrackQubit, StackMemorySimulator


def test_loss():

    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        squin.qubit_loss(1.0, q[0])
        return q[0]

    main.print()

    sim = StackMemorySimulator(min_qubits=1)
    qubit = sim.run(main)

    assert isinstance(qubit, PyQrackQubit)
    assert not qubit.is_active()


@pytest.mark.parametrize(
    "seed, expected_loss_triggered",
    [
        (0, False),  # Seed 0: no loss
        (2, True),  # Seed 2: qubits 0-3 are lost
    ],
)
def test_correlated_loss(seed, expected_loss_triggered):

    @squin.kernel
    def main():
        q = squin.qubit.new(5)
        squin.correlated_qubit_loss(0.5, q[0:4])
        return q

    rng = np.random.default_rng(seed=seed)
    sim = StackMemorySimulator(min_qubits=5, rng_state=rng)
    qubits = sim.run(main)

    for q in qubits:
        assert isinstance(q, PyQrackQubit)

    for q in qubits[:4]:
        assert not q.is_active() if expected_loss_triggered else q.is_active()

    assert qubits[4].is_active()


def test_bit_flip():

    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        squin.bit_flip(1.0, q[0])
        squin.single_qubit_pauli_channel(0.0, 1.0, 0.0, q[0])
        return squin.qubit.measure(q)

    sim = StackMemorySimulator(min_qubits=1)
    result = sim.run(main)
    assert result[0] == 0
