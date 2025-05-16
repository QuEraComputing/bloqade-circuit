from bloqade import squin
from bloqade.pyqrack import PyQrack, PyQrackQubit
from bloqade.squin.noise.stmts import NoiseChannel, StochasticUnitaryChannel


def test_pauli_error():
    @squin.noise_kernel
    def main():
        q = squin.qubit.new(1)
        x = squin.op.x()
        squin.qubit.apply(x, [q[0]])

        x_err = squin.noise.pauli_error(x, 0.1)
        squin.qubit.apply(x_err, [q[0]])
        return q

    main.print()

    # test if the rewrite was successful
    region = main.code.regions[0]
    count_unitary_noises = 0
    for stmt in region.stmts():
        assert not isinstance(stmt, NoiseChannel)
        count_unitary_noises += isinstance(stmt, StochasticUnitaryChannel)

    assert count_unitary_noises == 1

    # test the execution
    target = PyQrack(1)
    result = target.multi_run(main, 100)

    zero_avg = 0.0
    for res in result:
        assert isinstance(qubit := res[0], PyQrackQubit)
        ket = qubit.sim_reg.out_ket()
        zero_avg += abs(ket[0]) ** 2

    zero_avg /= len(result)

    # should be approximately 10% since that is the bit flip error probability in the kernel above
    assert 0.05 < zero_avg < 0.15


def test_qubit_loss():
    @squin.noise_kernel
    def main():
        q = squin.qubit.new(1)
        ql = squin.noise.qubit_loss(1.0)
        squin.qubit.apply(ql, q)
        return q

    target = PyQrack(1)
    result = target.run(main)

    assert isinstance(qubit := result[0], PyQrackQubit)
    assert not qubit.is_active()


def test_pauli_channel():
    @squin.noise_kernel
    def single_qubit():
        q = squin.qubit.new(1)
        pauli_channel = squin.noise.single_qubit_pauli_channel(params=(0.1, 0.2, 0.3))
        squin.qubit.apply(pauli_channel, q)
        return q

    single_qubit.print()

    target = PyQrack(1)
    target.run(single_qubit)

    @squin.noise_kernel
    def two_qubits():
        q = squin.qubit.new(2)
        pauli_channel = squin.noise.two_qubit_pauli_channel(
            params=(
                0.1,
                0.1,
                0.1,
                0.1,
                0.1,
                0.1,
                0.1,
                0.1,
                0.1,
                0.1,
                0.1,
                0.1,
                0.1,
                0.1,
                0.1,
            )
        )
        squin.qubit.apply(pauli_channel, q)
        return q

    two_qubits.print()

    target = PyQrack(2)
    target.run(two_qubits)
