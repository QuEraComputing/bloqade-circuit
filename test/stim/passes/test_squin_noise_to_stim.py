import io
import os

import kirin.types as kirin_types
from kirin import ir, types
from kirin.decl import info, statement
from kirin.rewrite import Walk
from kirin.dialects import ilist

from bloqade import stim, squin as sq
from bloqade.squin import noise, kernel
from bloqade.types import Qubit, QubitType
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStimPass, flatten
from bloqade.stim.rewrite import SquinNoiseToStim
from bloqade.squin.rewrite import WrapAddressAnalysis
from bloqade.analysis.address import AddressAnalysis


def codegen(mt: ir.Method):
    # method should not have any arguments!
    buf = io.StringIO()
    emit = EmitStimMain(dialects=stim.main, io=buf)
    emit.initialize()
    emit.run(mt)
    return buf.getvalue().strip()


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
        q = sq.qalloc(1)
        sq.single_qubit_pauli_channel(px=0.01, py=0.02, pz=0.03, qubit=q[0])
        return

    SquinToStimPass(test.dialects)(test)
    expected_stim_program = load_reference_program("apply_pauli_channel_1.stim")
    assert codegen(test) == expected_stim_program


def test_broadcast_pauli_channel_1():

    @kernel
    def test():
        q = sq.qalloc(10)
        sq.broadcast.single_qubit_pauli_channel(px=0.01, py=0.02, pz=0.03, qubits=q)
        return

    SquinToStimPass(test.dialects)(test)
    expected_stim_program = load_reference_program("broadcast_pauli_channel_1.stim")
    assert codegen(test) == expected_stim_program


def test_broadcast_pauli_channel_1_reuse():

    @kernel
    def fixed_1q_pauli_channel(qubits):
        sq.broadcast.single_qubit_pauli_channel(
            px=0.01, py=0.02, pz=0.03, qubits=qubits
        )

    @kernel
    def test():
        q = sq.qalloc(2)
        fixed_1q_pauli_channel(q)
        fixed_1q_pauli_channel(q)
        fixed_1q_pauli_channel(q)
        return

    SquinToStimPass(test.dialects)(test)
    expected_stim_program = load_reference_program(
        "broadcast_pauli_channel_1_reuse.stim"
    )
    assert codegen(test) == expected_stim_program


def test_broadcast_pauli_channel_2():

    @kernel
    def test():
        q = sq.qalloc(8)
        sq.broadcast.two_qubit_pauli_channel(
            probabilities=[
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
            ],
            controls=q[:4],
            targets=q[4:],
        )
        return

    SquinToStimPass(test.dialects)(test)
    expected_stim_program = load_reference_program("broadcast_pauli_channel_2.stim")
    assert codegen(test) == expected_stim_program


def test_broadcast_pauli_channel_2_reuse():

    @kernel
    def fixed_2q_pauli_channel(controls, targets):
        sq.broadcast.two_qubit_pauli_channel(
            probabilities=[
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
            ],
            controls=controls,
            targets=targets,
        )

    @kernel
    def test():
        q = sq.qalloc(8)

        fixed_2q_pauli_channel([q[0], q[1]], [q[2], q[3]])
        fixed_2q_pauli_channel([q[4], q[5]], [q[6], q[7]])
        return

    SquinToStimPass(test.dialects)(test)
    expected_stim_program = load_reference_program(
        "broadcast_pauli_channel_2_reuse.stim"
    )
    assert codegen(test) == expected_stim_program


def test_broadcast_depolarize2():

    @kernel
    def test():
        q = sq.qalloc(4)
        sq.broadcast.depolarize2(p=0.015, controls=q[:2], targets=q[2:])
        return

    SquinToStimPass(test.dialects)(test)
    expected_stim_program = load_reference_program("broadcast_depolarize2.stim")
    assert codegen(test) == expected_stim_program


def test_apply_depolarize1():

    @kernel
    def test():
        q = sq.qalloc(1)
        sq.depolarize(p=0.01, qubit=q[0])
        return

    SquinToStimPass(test.dialects)(test)
    expected_stim_program = load_reference_program("apply_depolarize1.stim")
    assert codegen(test) == expected_stim_program


def test_broadcast_depolarize1():

    @kernel
    def test():
        q = sq.qalloc(4)
        sq.broadcast.depolarize(p=0.01, qubits=q)
        return

    SquinToStimPass(test.dialects)(test)
    expected_stim_program = load_reference_program("broadcast_depolarize1.stim")
    assert codegen(test) == expected_stim_program


def test_apply_loss():

    @kernel
    def apply_loss(qubit):
        sq.qubit_loss(0.1, qubit=qubit)

    @kernel
    def test():
        q = sq.qalloc(3)
        apply_loss(q[0])
        apply_loss(q[1])
        apply_loss(q[2])

    SquinToStimPass(test.dialects)(test)

    expected_stim_program = load_reference_program("apply_loss.stim")
    assert codegen(test) == expected_stim_program


def test_correlated_qubit_loss():
    @kernel
    def test():
        q = sq.qalloc(3)
        sq.correlated_qubit_loss(0.1, qubits=q[:2])

    SquinToStimPass(test.dialects)(test)

    expected = "I_ERROR[correlated_loss:0](0.10000000) 0 1"
    assert codegen(test) == expected


def test_broadcast_correlated_qubit_loss():
    @kernel
    def test():
        q1 = sq.qalloc(3)
        q2 = sq.qalloc(3)
        sq.broadcast.correlated_qubit_loss(0.1, qubits=[q1, q2])

    SquinToStimPass(test.dialects)(test)

    expected = (
        "I_ERROR[correlated_loss:0](0.10000000) 0 1 2\n"
        "I_ERROR[correlated_loss:1](0.10000000) 3 4 5"
    )
    assert codegen(test) == expected


def test_correlated_qubit_loss_codegen_with_offset():

    @kernel
    def test():
        q = sq.qalloc(4)
        sq.correlated_qubit_loss(0.1, qubits=q)

    SquinToStimPass(test.dialects)(test)

    emit = EmitStimMain(correlation_identifier_offset=10)
    emit.initialize()
    emit.run(mt=test, args=())
    stim_str = emit.get_output().strip()
    assert stim_str == "I_ERROR[correlated_loss:10](0.10000000) 0 1 2 3"


def get_stmt_at_idx(method: ir.Method, idx: int) -> ir.Statement:
    return method.callable_region.blocks[0].stmts.at(idx)


# If there's no concrete qubit values from the address analysis then
# the rewrite rule should immediately return and not mutate the method.
def test_no_qubit_address_available():

    @kernel
    def test(q: ilist.IList[Qubit, kirin_types.Literal]):
        sq.single_qubit_pauli_channel(px=0.01, py=0.02, pz=0.03, qubit=q[0])
        return

    flatten.Flatten(dialects=test.dialects).fixpoint(test)
    Walk(SquinNoiseToStim()).rewrite(test.code)

    expected_1q_noise_pauli_channel = get_stmt_at_idx(test, 6)

    assert isinstance(
        expected_1q_noise_pauli_channel, noise.stmts.SingleQubitPauliChannel
    )


def test_nonexistent_noise_channel():

    @statement(dialect=noise.dialect)
    class NonExistentNoiseChannel(noise.stmts.NoiseChannel):
        """
        A non-existent noise channel for testing purposes.
        """

        qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, types.Any])

        pass

    @kernel
    def test():
        q = sq.qalloc(1)
        NonExistentNoiseChannel(qubits=q)
        return

    frame, _ = AddressAnalysis(test.dialects).run(test)
    WrapAddressAnalysis(address_analysis=frame.entries).rewrite(test.code)

    rewrite_result = Walk(SquinNoiseToStim()).rewrite(test.code)

    expected_noise_channel_stmt = get_stmt_at_idx(test, 2)

    # The rewrite shouldn't have occurred at all because there is no rewrite logic for
    # NonExistentNoiseChannel.
    assert not rewrite_result.has_done_something
    assert isinstance(expected_noise_channel_stmt, NonExistentNoiseChannel)


def test_standard_op_no_rewrite():

    @kernel
    def test():
        q = sq.qalloc(1)
        sq.x(qubit=q[0])
        return

    frame, _ = AddressAnalysis(test.dialects).run(test)
    WrapAddressAnalysis(address_analysis=frame.entries).rewrite(test.code)

    rewrite_result = Walk(SquinNoiseToStim()).rewrite(test.code)

    # Rewrite should not have done anything because target is not a noise channel
    assert not rewrite_result.has_done_something
