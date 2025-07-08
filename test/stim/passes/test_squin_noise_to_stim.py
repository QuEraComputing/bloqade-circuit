import os

from kirin import ir

from bloqade.squin import noise, qubit, kernel

from .test_squin_qubit_to_stim import codegen as _codegen, run_address_and_stim_passes


def codegen(mt: ir.Method) -> str:
    """Generate stim code."""
    return _codegen(mt).strip()


def load_reference_program(filename):
    """Load stim file."""
    path = os.path.join(
        os.path.dirname(__file__), "stim_reference_programs", "noise", filename
    )
    with open(path, "r") as f:
        return f.read().strip()


def test_apply_pauli_channel_1():

    @kernel
    def test():
        q = qubit.new(1)
        channel = noise.single_qubit_pauli_channel(params=[0.01, 0.02, 0.03])
        qubit.apply(channel, q[0])
        return

    run_address_and_stim_passes(test)
    expected_stim_program = load_reference_program("apply_pauli_channel_1.stim")
    assert codegen(test) == expected_stim_program


def test_broadcast_pauli_channel_1():

    @kernel
    def test():
        q = qubit.new(1)
        channel = noise.single_qubit_pauli_channel(params=[0.01, 0.02, 0.03])
        qubit.broadcast(channel, q)
        return

    run_address_and_stim_passes(test)
    expected_stim_program = load_reference_program("broadcast_pauli_channel_1.stim")
    assert codegen(test) == expected_stim_program


def test_broadcast_pauli_channel_1_many_qubits():

    @kernel
    def test():
        q = qubit.new(2)
        channel = noise.single_qubit_pauli_channel(params=[0.01, 0.02, 0.03])
        qubit.broadcast(channel, q)
        return

    run_address_and_stim_passes(test)
    expected_stim_program = load_reference_program(
        "broadcast_pauli_channel_1_many_qubits.stim"
    )
    assert codegen(test) == expected_stim_program


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
    expected_stim_program = load_reference_program(
        "broadcast_pauli_channel_1_reuse.stim"
    )
    assert codegen(test) == expected_stim_program


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
    expected_stim_program = load_reference_program("broadcast_pauli_channel_2.stim")
    assert codegen(test) == expected_stim_program


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
    expected_stim_program = load_reference_program(
        "broadcast_pauli_channel_2_reuse_on_4_qubits.stim"
    )
    assert codegen(test) == expected_stim_program
