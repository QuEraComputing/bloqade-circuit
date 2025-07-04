from bloqade.squin import noise, qubit, kernel

from .test_squin_qubit_to_stim import codegen, run_address_and_stim_passes


def test_apply_pauli_channel_1():

    @kernel
    def test():
        q = qubit.new(1)
        channel = noise.single_qubit_pauli_channel(params=[0.01, 0.02, 0.03])
        qubit.apply(channel, q[0])
        return

    run_address_and_stim_passes(test)
    assert codegen(test).strip() == (
        "PAULI_CHANNEL_1(0.01000000, 0.02000000, 0.03000000) 0"
    )


def test_broadcast_pauli_channel_1():

    @kernel
    def test():
        q = qubit.new(1)
        channel = noise.single_qubit_pauli_channel(params=[0.01, 0.02, 0.03])
        qubit.broadcast(channel, q)
        return

    run_address_and_stim_passes(test)
    assert codegen(test).strip() == (
        "PAULI_CHANNEL_1(0.01000000, 0.02000000, 0.03000000) 0"
    )


def test_broadcast_pauli_channel_1_many_qubits():

    @kernel
    def test():
        q = qubit.new(2)
        channel = noise.single_qubit_pauli_channel(params=[0.01, 0.02, 0.03])
        qubit.broadcast(channel, q)
        return

    run_address_and_stim_passes(test)
    assert codegen(test).strip() == (
        "PAULI_CHANNEL_1(0.01000000, 0.02000000, 0.03000000) 0 1"
    )


def test_broadcast_pauli_channel_1_reuse():

    @kernel
    def test():
        q = qubit.new(1)
        channel = noise.single_qubit_pauli_channel(params=[0.01, 0.02, 0.03])
        qubit.broadcast(channel, q)
        qubit.broadcast(channel, q)
        qubit.broadcast(channel, q)
        return

    run_address_and_stim_passes(test)
    assert codegen(test).strip() == "\n".join(
        [
            "PAULI_CHANNEL_1(0.01000000, 0.02000000, 0.03000000) 0",
            "PAULI_CHANNEL_1(0.01000000, 0.02000000, 0.03000000) 0",
            "PAULI_CHANNEL_1(0.01000000, 0.02000000, 0.03000000) 0",
        ]
    )


def test_broadcast_pauli_channel_2():

    @kernel
    def test():
        q = qubit.new(2)
        channel = noise.two_qubit_pauli_channel(
            params=[
                0.001,
                0.002,
                0.003,
                0.004,
                0.005,
                0.006,
                0.007,
                0.008,
                0.009,
                0.010,
                0.011,
                0.012,
                0.013,
                0.014,
                0.015,
            ]
        )
        qubit.broadcast(channel, q)
        return

    run_address_and_stim_passes(test)
    assert codegen(test).strip() == (
        "PAULI_CHANNEL_2("
        "0.00100000, 0.00200000, 0.00300000, 0.00400000, 0.00500000, "
        "0.00600000, 0.00700000, 0.00800000, 0.00900000, 0.01000000, "
        "0.01100000, 0.01200000, 0.01300000, 0.01400000, 0.01500000"
        ") 0 1"
    )


def test_broadcast_pauli_channel_2_reuse_on_4_qubits():

    @kernel
    def test():
        q = qubit.new(4)
        channel = noise.two_qubit_pauli_channel(
            params=[
                0.001,
                0.002,
                0.003,
                0.004,
                0.005,
                0.006,
                0.007,
                0.008,
                0.009,
                0.010,
                0.011,
                0.012,
                0.013,
                0.014,
                0.015,
            ]
        )
        qubit.broadcast(channel, [q[0], q[1]])
        qubit.broadcast(channel, [q[2], q[3]])
        return

    run_address_and_stim_passes(test)
    assert codegen(test).strip() == "\n".join(
        [
            "PAULI_CHANNEL_2("
            "0.00100000, 0.00200000, 0.00300000, 0.00400000, 0.00500000, "
            "0.00600000, 0.00700000, 0.00800000, 0.00900000, 0.01000000, "
            "0.01100000, 0.01200000, 0.01300000, 0.01400000, 0.01500000"
            ") 0 1",
            "PAULI_CHANNEL_2("
            "0.00100000, 0.00200000, 0.00300000, 0.00400000, 0.00500000, "
            "0.00600000, 0.00700000, 0.00800000, 0.00900000, 0.01000000, "
            "0.01100000, 0.01200000, 0.01300000, 0.01400000, 0.01500000"
            ") 2 3",
        ]
    )
