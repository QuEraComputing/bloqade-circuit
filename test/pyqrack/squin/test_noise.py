import math

from bloqade import squin
from bloqade.pyqrack import PyQrack, PyQrackQubit, StackMemorySimulator
from bloqade.squin.noise.stmts import NoiseChannel, StochasticUnitaryChannel
from bloqade.squin.noise.rewrite import RewriteNoiseStmts

rewrite_noise_pass = RewriteNoiseStmts(squin.kernel)


def test_pauli_error():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        x = squin.op.x()
        squin.qubit.apply(x, [q[0]])

        x_err = squin.noise.pauli_error(x, 0.1)
        squin.qubit.apply(x_err, [q[0]])
        return q

    rewrite_noise_pass(main)

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
    assert 0.0 < zero_avg < 0.25


def test_qubit_loss():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        ql = squin.noise.qubit_loss(1.0)
        squin.qubit.apply(ql, q)
        return q

    rewrite_noise_pass(main)

    target = PyQrack(1)
    result = target.run(main)

    assert isinstance(qubit := result[0], PyQrackQubit)
    assert not qubit.is_active()


def test_pauli_channel():
    @squin.kernel
    def single_qubit():
        q = squin.qubit.new(1)
        pauli_channel = squin.noise.single_qubit_pauli_channel(params=(0.1, 0.2, 0.3))
        squin.qubit.apply(pauli_channel, q)
        return q

    rewrite_noise_pass(single_qubit)

    single_qubit.print()

    target = PyQrack(1)
    target.run(single_qubit)

    @squin.kernel
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

    rewrite_noise_pass(two_qubits)

    two_qubits.print()

    target = PyQrack(2)
    target.run(two_qubits)


def test_depolarize():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        h = squin.op.h()
        squin.qubit.apply(h, q)

        depolar = squin.noise.depolarize(0.1)
        squin.qubit.apply(depolar, q)
        return q

    rewrite_noise_pass(main)

    main.print()

    target = PyQrack(1)
    target.run(main)


def test_without_rewrite():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        x = squin.op.x()
        squin.qubit.apply(x, q[0])

        x_err = squin.noise.pauli_error(x, 0.1)
        squin.qubit.apply(x_err, q[0])
        return q

    sim = StackMemorySimulator(min_qubits=1)
    sim.state_vector(main)

    main.print()

    # make sure the method wasn't updated in-place
    stmts = list(main.callable_region.blocks[0].stmts)
    assert sum([isinstance(s, StochasticUnitaryChannel) for s in stmts]) == 0
    assert sum([isinstance(s, squin.noise.stmts.PauliError) for s in stmts]) == 1


def test_pauli_string_error():
    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        x = squin.op.x()

        err = squin.noise.pauli_error(x, 1.0)
        squin.qubit.apply(err, q[0])

        s = squin.op.pauli_string(string="XX")
        err2 = squin.noise.pauli_error(s, 1.0)
        squin.qubit.apply(err2, q)

    main.print()

    RewriteNoiseStmts(main.dialects)(main)

    main.print()

    sim = StackMemorySimulator(min_qubits=2)

    ket = sim.state_vector(main)

    print(ket)

    assert math.isclose(abs(ket[2]) ** 2, 1.0, abs_tol=1e-5)


def test_depolarize2():
    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        err = squin.noise.depolarize2(0.1)
        squin.qubit.apply(err, q[0], q[1])

    main.print()

    main_ = main.similar(main.dialects)

    result = RewriteNoiseStmts(main.dialects)(main_)
    assert result.has_done_something
    main_.print()

    sim = StackMemorySimulator(min_qubits=2)
    sim.run(main)
