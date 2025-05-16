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
