from bloqade import squin
from bloqade.pyqrack import PyQrack, PyQrackQubit, StackMemorySimulator


def test_qubit_loss():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        squin.qubit_loss(1.0, q[0])
        return q

    target = PyQrack(1)
    result = target.run(main)

    assert isinstance(qubit := result[0], PyQrackQubit)
    assert not qubit.is_active()


def test_correlated_loss():
    @squin.kernel
    def main():
        q = squin.qubit.new(5)
        squin.correlated_qubit_loss(0.5, q[0:4])
        return q

    target = PyQrack(5)
    for _ in range(10):
        qubits = target.run(main)
        qubits_active = [q.is_active() for q in qubits[:4]]
        assert all(qubits_active) or not any(qubits_active)

        assert qubits[4].is_active()


def test_pauli_channel():
    @squin.kernel
    def single_qubit():
        q = squin.qubit.new(1)
        squin.single_qubit_pauli_channel(px=0.1, py=0.2, pz=0.3, qubit=q[0])
        return q

    single_qubit.print()

    target = PyQrack(1)
    target.run(single_qubit)

    @squin.kernel
    def two_qubits():
        q = squin.qubit.new(2)
        squin.two_qubit_pauli_channel(
            [
                0.01,
                0.01,
                0.01,
                0.01,
                0.01,
                0.01,
                0.01,
                0.01,
                0.01,
                0.01,
                0.01,
                0.01,
                0.01,
                0.01,
                0.01,
            ],
            q[0],
            q[1],
        )
        return q

    two_qubits.print()

    target = PyQrack(2)
    target.run(two_qubits)


def test_depolarize():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        squin.h(q[0])

        squin.depolarize(0.1, q[0])
        return q

    main.print()

    target = PyQrack(1)
    target.run(main)


def test_depolarize2():
    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        squin.depolarize2(0.1, q[0], q[1])

    main.print()

    sim = StackMemorySimulator(min_qubits=2)
    sim.run(main)
