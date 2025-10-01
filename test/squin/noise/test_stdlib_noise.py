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
