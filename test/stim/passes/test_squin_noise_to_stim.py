from bloqade.squin import noise, qubit, kernel

from .test_squin_qubit_to_stim import codegen, run_address_and_stim_passes


def test_pauli_channel_1():

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


def test_pauli_channel_1_reuse():

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
