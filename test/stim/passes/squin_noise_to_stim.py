import os

import kirin.types as kirin_types
from kirin import ir, types
from kirin.decl import statement
from kirin.rewrite import Walk
from kirin.dialects import py, func, ilist

import bloqade.types as bloqade_types
from bloqade.squin import op, wire, noise, qubit, kernel
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStimPass
from bloqade.stim.rewrite import SquinNoiseToStim
from bloqade.squin.rewrite import WrapAddressAnalysis
from bloqade.analysis.address import AddressAnalysis

extended_kernel = kernel.add(wire)


def gen_func_from_stmts(stmts, output_type=types.NoneType):

    block = ir.Block(stmts)
    block.args.append_from(types.MethodType[[], types.NoneType], "main")
    func_wrapper = func.Function(
        sym_name="main",
        signature=func.Signature(inputs=(), output=output_type),
        body=ir.Region(blocks=block),
    )

    constructed_method = ir.Method(
        mod=None,
        py_func=None,
        sym_name="main",
        dialects=extended_kernel,
        code=func_wrapper,
        arg_names=[],
    )

    return constructed_method


def as_int(value: int):
    return py.constant.Constant(value=value)


def as_float(value: float):
    return py.constant.Constant(value=value)


def codegen(mt: ir.Method):
    # method should not have any arguments!
    emit = EmitStimMain()
    emit.initialize()
    emit.run(mt=mt, args=())
    return emit.get_output().strip()


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

    SquinToStimPass(test.dialects)(test)
    expected_stim_program = load_reference_program("apply_pauli_channel_1.stim")
    assert codegen(test) == expected_stim_program


def test_broadcast_pauli_channel_1():

    @kernel
    def test():
        q = qubit.new(1)
        channel = noise.single_qubit_pauli_channel(params=[0.01, 0.02, 0.03])
        qubit.broadcast(channel, q)
        return

    SquinToStimPass(test.dialects)(test)
    expected_stim_program = load_reference_program("broadcast_pauli_channel_1.stim")
    assert codegen(test) == expected_stim_program


def test_broadcast_pauli_channel_1_many_qubits():

    @kernel
    def test():
        q = qubit.new(2)
        channel = noise.single_qubit_pauli_channel(params=[0.01, 0.02, 0.03])
        qubit.broadcast(channel, q)
        return

    SquinToStimPass(test.dialects)(test)
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

    SquinToStimPass(test.dialects)(test)
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

    SquinToStimPass(test.dialects)(test)
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

    SquinToStimPass(test.dialects)(test)
    expected_stim_program = load_reference_program(
        "broadcast_pauli_channel_2_reuse_on_4_qubits.stim"
    )
    assert codegen(test) == expected_stim_program


def test_broadcast_depolarize2():

    @kernel
    def test():
        q = qubit.new(2)
        channel = noise.depolarize2(p=0.015)
        qubit.broadcast(channel, q)
        return

    SquinToStimPass(test.dialects)(test)
    expected_stim_program = load_reference_program("broadcast_depolarize2.stim")
    assert codegen(test) == expected_stim_program


def test_apply_depolarize1():

    @kernel
    def test():
        q = qubit.new(1)
        channel = noise.depolarize(p=0.01)
        qubit.apply(channel, q[0])
        return

    SquinToStimPass(test.dialects)(test)
    expected_stim_program = load_reference_program("apply_depolarize1.stim")
    assert codegen(test) == expected_stim_program


def test_broadcast_depolarize1():

    @kernel
    def test():
        q = qubit.new(4)
        channel = noise.depolarize(p=0.01)
        qubit.broadcast(channel, q)
        return

    SquinToStimPass(test.dialects)(test)
    expected_stim_program = load_reference_program("broadcast_depolarize1.stim")
    assert codegen(test) == expected_stim_program


def test_broadcast_iid_bit_flip_channel():

    @kernel
    def test():
        q = qubit.new(4)
        x = op.x()
        channel = noise.pauli_error(x, 0.01)
        qubit.broadcast(channel, q)
        return

    SquinToStimPass(test.dialects)(test)
    expected_stim_program = load_reference_program(
        "broadcast_iid_bit_flip_channel.stim"
    )
    assert codegen(test) == expected_stim_program


def test_broadcast_iid_phase_flip_channel():

    @kernel
    def test():
        q = qubit.new(4)
        z = op.z()
        channel = noise.pauli_error(z, 0.01)
        qubit.broadcast(channel, q)
        return

    SquinToStimPass(test.dialects)(test)
    expected_stim_program = load_reference_program(
        "broadcast_iid_phase_flip_channel.stim"
    )
    assert codegen(test) == expected_stim_program


def test_broadcast_iid_y_flip_channel():

    @kernel
    def test():
        q = qubit.new(4)
        y = op.y()
        channel = noise.pauli_error(y, 0.01)
        qubit.broadcast(channel, q)
        return

    SquinToStimPass(test.dialects)(test)
    expected_stim_program = load_reference_program("broadcast_iid_y_flip_channel.stim")
    assert codegen(test) == expected_stim_program


def test_apply_loss():

    @kernel
    def test():
        q = qubit.new(3)
        loss = noise.qubit_loss(0.1)
        qubit.apply(loss, q[0])
        qubit.apply(loss, q[1])
        qubit.apply(loss, q[2])

    SquinToStimPass(test.dialects)(test)

    expected_stim_program = load_reference_program("apply_loss.stim")
    assert codegen(test) == expected_stim_program


def test_wire_apply_pauli_channel_1():

    stmts: list[ir.Statement] = [
        (n_qubits := as_int(1)),
        (q := qubit.New(n_qubits=n_qubits.result)),
        (idx0 := as_int(0)),
        (q0 := py.indexing.GetItem(obj=q.result, index=idx0.result)),
        (w0 := wire.Unwrap(qubit=q0.result)),
        # apply noise other than qubit loss
        (prob_x := as_float(0.01)),
        (prob_y := as_float(0.01)),
        (prob_z := as_float(0.01)),
        (
            noise_params := ilist.New(
                values=(prob_x.result, prob_y.result, prob_z.result)
            )
        ),
        (
            pauli_channel_1q := noise.stmts.SingleQubitPauliChannel(
                params=noise_params.result
            )
        ),
        (app0 := wire.Apply(pauli_channel_1q.result, w0.result)),
        (wire.Wrap(app0.results[0], q0.result)),
        (ret_none := func.ConstantNone()),
        (func.Return(ret_none)),
    ]

    test_method = gen_func_from_stmts(stmts)

    SquinToStimPass(test_method.dialects)(test_method)

    expected_stim_program = load_reference_program("wire_apply_pauli_channel_1.stim")
    assert codegen(test_method) == expected_stim_program


def get_stmt_at_idx(method: ir.Method, idx: int) -> ir.Statement:
    return method.callable_region.blocks[0].stmts.at(idx)


# If there's no concrete qubit values from the address analysis then
# the rewrite rule should immediately return and not mutate the method.
def test_no_qubit_address_available():

    @kernel
    def test(q: ilist.IList[bloqade_types.Qubit, kirin_types.Literal]):
        channel = noise.single_qubit_pauli_channel(params=[0.01, 0.02, 0.03])
        qubit.apply(channel, q[0])
        return

    Walk(SquinNoiseToStim()).rewrite(test.code)

    expected_noise_channel_stmt = get_stmt_at_idx(test, 1)
    expected_qubit_apply_stmt = get_stmt_at_idx(test, 4)

    assert isinstance(expected_noise_channel_stmt, noise.stmts.SingleQubitPauliChannel)
    assert isinstance(expected_qubit_apply_stmt, qubit.Apply)


def test_nonexistent_noise_channel():

    @statement(dialect=noise.dialect)
    class NonExistentNoiseChannel(noise.stmts.NoiseChannel):
        """
        A non-existent noise channel for testing purposes.
        """

        pass

    @kernel
    def test():
        q = qubit.new(1)
        channel = NonExistentNoiseChannel()
        qubit.apply(channel, q[0])
        return

    frame, _ = AddressAnalysis(test.dialects).run_analysis(test)
    WrapAddressAnalysis(address_analysis=frame.entries).rewrite(test.code)

    rewrite_result = Walk(SquinNoiseToStim()).rewrite(test.code)

    expected_noise_channel_stmt = get_stmt_at_idx(test, 2)
    expected_qubit_apply_stmt = get_stmt_at_idx(test, 5)

    # The rewrite shouldn't have occurred at all because there is no rewrite logic for
    # NonExistentNoiseChannel.
    assert not rewrite_result.has_done_something
    assert isinstance(expected_noise_channel_stmt, NonExistentNoiseChannel)
    assert isinstance(expected_qubit_apply_stmt, qubit.Apply)


def test_standard_op_no_rewrite():

    @kernel
    def test():
        q = qubit.new(1)
        qubit.apply(op.x(), q[0])
        return

    frame, _ = AddressAnalysis(test.dialects).run_analysis(test)
    WrapAddressAnalysis(address_analysis=frame.entries).rewrite(test.code)

    rewrite_result = Walk(SquinNoiseToStim()).rewrite(test.code)

    # Rewrite should not have done anything because target is not a noise channel
    assert not rewrite_result.has_done_something
