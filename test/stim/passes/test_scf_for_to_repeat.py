import io
import os

from kirin import ir
from kirin.dialects import ilist

from bloqade import stim, squin
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStimPass


def codegen(mt: ir.Method):
    buf = io.StringIO()
    emit = EmitStimMain(dialects=stim.main, io=buf)
    emit.initialize()
    emit.run(mt)
    return buf.getvalue().strip()


def load_reference_program(filename):
    path = os.path.join(
        os.path.dirname(__file__), "stim_reference_programs", "scf_for", filename
    )
    with open(path, "r") as f:
        return f.read()


def test_repeat_on_gates_only():
    @squin.kernel
    def test():
        qs = squin.qalloc(3)
        squin.broadcast.reset(qs)
        for _ in range(5):
            squin.broadcast.h(qs)
            squin.broadcast.x(qs)
            squin.cz(control=qs[0], target=qs[1])
            squin.depolarize(p=0.01, qubit=qs[0])
            squin.qubit_loss(p=0.02, qubit=qs[1])
            squin.broadcast.qubit_loss(p=0.03, qubits=qs)

    SquinToStimPass(dialects=test.dialects)(test)
    assert codegen(test) == load_reference_program("repeat_on_gates_only.stim").rstrip()


def test_repetition_code_structure():
    @squin.kernel
    def test():
        qs = squin.qalloc(3)
        curr_ms = squin.broadcast.measure(qs)
        for _ in range(5):
            prev_ms = curr_ms
            squin.broadcast.h(qs)
            curr_ms = squin.broadcast.measure(qs)
            squin.set_detector(
                measurements=[curr_ms[0], prev_ms[0]], coordinates=[0, 0]
            )
        final_ms = squin.broadcast.measure(qs)
        squin.set_detector(measurements=[final_ms[0], curr_ms[0]], coordinates=[1, 0])
        squin.set_observable([final_ms[0]])

    SquinToStimPass(dialects=test.dialects)(test)
    assert codegen(test) == load_reference_program("rep_code_structure.stim").rstrip()


def test_full_repetition_code():
    @squin.kernel
    def test():
        qs = squin.qalloc(5)
        data_qs = [qs[0], qs[2], qs[4]]
        and_qs = [qs[1], qs[3]]
        squin.broadcast.reset(qs)
        squin.broadcast.cx(controls=[qs[0], qs[2]], targets=[qs[1], qs[3]])
        squin.broadcast.cx(controls=[qs[2], qs[4]], targets=[qs[1], qs[3]])
        curr_ms = squin.broadcast.measure(and_qs)
        squin.set_detector([curr_ms[0]], coordinates=[0, 0])
        squin.set_detector([curr_ms[1]], coordinates=(0, 1))
        for _ in range(10):
            prev_ms = curr_ms
            squin.broadcast.cx(controls=[qs[0], qs[2]], targets=[qs[1], qs[3]])
            squin.broadcast.cx(controls=[qs[2], qs[4]], targets=[qs[1], qs[3]])
            curr_ms = squin.broadcast.measure(and_qs)
            squin.annotate.set_detector([prev_ms[0], curr_ms[0]], coordinates=[0, 0])
            squin.annotate.set_detector([prev_ms[1], curr_ms[1]], coordinates=(0, 1))
        data_ms = squin.broadcast.measure(data_qs)
        squin.set_detector([data_ms[0], data_ms[1], curr_ms[0]], coordinates=[2, 0])
        squin.set_detector([data_ms[2], data_ms[1], curr_ms[1]], coordinates=(2, 1))
        squin.set_observable([data_ms[2]])

    SquinToStimPass(dialects=test.dialects)(test)
    assert codegen(test) == load_reference_program("rep_code.stim").rstrip()


def test_feedforward_inside_loop():
    @squin.kernel
    def test():
        qs = squin.qalloc(5)
        curr_ms = squin.broadcast.measure(qs)
        for _ in range(3):
            prev_ms = curr_ms
            if squin.is_one(prev_ms[0]):
                squin.y(qs[0])
            if squin.is_one(prev_ms[1]):
                squin.x(qs[1])
                squin.z(qs[2])
            curr_ms = squin.broadcast.measure(qs)
        squin.set_detector([curr_ms[0]], coordinates=[0, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test) == load_reference_program("feedforward_inside_loop.stim").rstrip()
    )


def test_nested_unroll():
    @squin.kernel
    def test():
        qs = squin.qalloc(5)
        curr_ms = squin.broadcast.measure(qubits=qs)
        for _ in range(100):
            prev_ms = curr_ms
            squin.broadcast.h(qs)
            curr_ms = squin.broadcast.measure(qs)
            squin.broadcast.reset(qs)
            for i in range(len(curr_ms)):
                squin.set_detector(
                    measurements=[curr_ms[i], prev_ms[i]], coordinates=[0, 0]
                )
        data_ms = squin.broadcast.measure(qs)
        squin.set_detector(
            measurements=[data_ms[0], data_ms[1], curr_ms[0]], coordinates=[0, 0]
        )
        squin.set_observable(measurements=[data_ms[3]])

    SquinToStimPass(dialects=test.dialects)(test)
    assert codegen(test) == load_reference_program("test_nested_unroll.stim").rstrip()


def test_surface_code_memory():
    @squin.kernel
    def surface_code_kernel():
        qs = squin.qalloc(17)
        squin.broadcast.reset(qs)
        x_ancillas = [qs[0], qs[5], qs[11], qs[16]]
        squin.broadcast.h(x_ancillas)
        cx_cycle_1_ctrls = [qs[0], qs[5], qs[8], qs[11], qs[13], qs[15]]
        cx_cycle_1_targs = [qs[2], qs[4], qs[9], qs[10], qs[12], qs[14]]
        cx_cycle_2_ctrls = [qs[0], qs[2], qs[5], qs[7], qs[9], qs[11]]
        cx_cycle_2_targs = [qs[1], qs[4], qs[8], qs[10], qs[12], qs[13]]
        cx_cycle_3_ctrls = [qs[5], qs[7], qs[9], qs[11], qs[13], qs[16]]
        cx_cycle_3_targs = [qs[3], qs[4], qs[6], qs[8], qs[12], qs[15]]
        cx_cycle_4_ctrls = [qs[1], qs[3], qs[5], qs[8], qs[11], qs[16]]
        cx_cycle_4_targs = [qs[2], qs[4], qs[6], qs[7], qs[12], qs[14]]
        squin.broadcast.cx(controls=cx_cycle_1_ctrls, targets=cx_cycle_1_targs)
        squin.broadcast.cx(controls=cx_cycle_2_ctrls, targets=cx_cycle_2_targs)
        squin.broadcast.cx(controls=cx_cycle_3_ctrls, targets=cx_cycle_3_targs)
        squin.broadcast.cx(controls=cx_cycle_4_ctrls, targets=cx_cycle_4_targs)
        squin.broadcast.h(x_ancillas)
        ancilla_qs = [qs[0], qs[4], qs[5], qs[6], qs[10], qs[11], qs[12], qs[16]]
        curr_ancilla_ms = squin.broadcast.measure(qubits=ancilla_qs)
        squin.broadcast.reset(ancilla_qs)
        z_ancillas_ms = [
            curr_ancilla_ms[1],
            curr_ancilla_ms[3],
            curr_ancilla_ms[4],
            curr_ancilla_ms[6],
        ]
        for i in range(len(z_ancillas_ms)):
            squin.set_detector(measurements=[z_ancillas_ms[i]], coordinates=[0, 0])
        for _ in range(100):
            prev_ancilla_ms = curr_ancilla_ms
            squin.broadcast.h(x_ancillas)
            squin.broadcast.cx(controls=cx_cycle_1_ctrls, targets=cx_cycle_1_targs)
            squin.broadcast.cx(controls=cx_cycle_2_ctrls, targets=cx_cycle_2_targs)
            squin.broadcast.cx(controls=cx_cycle_3_ctrls, targets=cx_cycle_3_targs)
            squin.broadcast.cx(controls=cx_cycle_4_ctrls, targets=cx_cycle_4_targs)
            curr_ancilla_ms = squin.broadcast.measure(qubits=ancilla_qs)
            squin.broadcast.reset(ancilla_qs)
            for i in range(len(curr_ancilla_ms)):
                squin.set_detector(
                    measurements=[curr_ancilla_ms[i], prev_ancilla_ms[i]],
                    coordinates=[0, 0],
                )
        data_qs = [qs[1], qs[2], qs[3], qs[7], qs[8], qs[9], qs[13], qs[14], qs[15]]
        data_ms = squin.broadcast.measure(qubits=data_qs)
        squin.set_detector(
            measurements=[data_ms[6], data_ms[3], curr_ancilla_ms[4]],
            coordinates=[0, 0],
        )
        squin.set_detector(
            measurements=[
                data_ms[4],
                data_ms[3],
                data_ms[1],
                data_ms[0],
                curr_ancilla_ms[1],
            ],
            coordinates=[0, 0],
        )
        squin.set_detector(
            measurements=[
                data_ms[8],
                data_ms[7],
                data_ms[5],
                data_ms[4],
                curr_ancilla_ms[6],
            ],
            coordinates=[0, 0],
        )
        squin.set_detector(
            measurements=[data_ms[5], data_ms[2], curr_ancilla_ms[3]],
            coordinates=[0, 0],
        )
        squin.set_observable(measurements=[data_ms[0], data_ms[1], data_ms[2]])

    SquinToStimPass(dialects=surface_code_kernel.dialects)(surface_code_kernel)
    assert (
        codegen(surface_code_kernel)
        == load_reference_program("surface_code_memory.stim").rstrip()
    )


def test_color_code_memory_init():
    @squin.kernel
    def color_code_kernel_init():
        def c_xyz(qs):
            squin.broadcast.s(qs)
            squin.broadcast.s(qs)
            squin.broadcast.s(qs)
            squin.broadcast.h(qs)

        qs = squin.qalloc(10)
        squin.broadcast.reset(qs)
        for _ in range(2):
            ilist.map(c_xyz, [qs[0], qs[1], qs[3], qs[5], qs[6], qs[7], qs[9]])
            squin.broadcast.cx(controls=[qs[5], qs[3]], targets=[qs[4], qs[2]])
            squin.broadcast.cx(controls=[qs[7], qs[6]], targets=[qs[4], qs[2]])
            squin.broadcast.cx(controls=[qs[1], qs[6]], targets=[qs[4], qs[8]])
            squin.broadcast.cx(controls=[qs[1], qs[7]], targets=[qs[2], qs[8]])
            squin.broadcast.cx(controls=[qs[5], qs[9]], targets=[qs[2], qs[8]])
            squin.broadcast.cx(controls=[qs[0], qs[5]], targets=[qs[4], qs[8]])
            squin.broadcast.measure([qs[2], qs[4], qs[8]])
            squin.broadcast.reset([qs[2], qs[4], qs[8]])

    SquinToStimPass(dialects=color_code_kernel_init.dialects)(color_code_kernel_init)
    assert (
        codegen(color_code_kernel_init)
        == load_reference_program("color_code_init.stim").rstrip()
    )


def test_accumulator_append_empty_init():
    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = []
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program("accumulator_append_empty_init.stim").rstrip()
    )


def test_accumulator_prepend_empty_init():
    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = []
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program("accumulator_prepend_empty_init.stim").rstrip()
    )


def test_accumulator_append_initialized():
    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program("accumulator_append_initialized.stim").rstrip()
    )


def test_accumulator_prepend_initialized():
    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program("accumulator_prepend_initialized.stim").rstrip()
    )


def test_accumulator_append_empty_init_all_iters():
    """Accessing measurements from every iteration, not just the first."""

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = []
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])
        squin.set_detector([acc[2], acc[3]], coordinates=[1, 0])
        squin.set_detector([acc[4], acc[5]], coordinates=[2, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program(
            "accumulator_append_empty_init_all_iters.stim"
        ).rstrip()
    )


def test_accumulator_prepend_empty_init_all_iters():
    """Accessing measurements from every iteration via prepend, not just the last."""

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = []
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])
        squin.set_detector([acc[2], acc[3]], coordinates=[1, 0])
        squin.set_detector([acc[4], acc[5]], coordinates=[2, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program(
            "accumulator_prepend_empty_init_all_iters.stim"
        ).rstrip()
    )


def test_accumulator_append_initialized_all_iters():
    """Accessing measurements from initial + every loop iteration."""

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])
        squin.set_detector([acc[2], acc[3]], coordinates=[1, 0])
        squin.set_detector([acc[4], acc[5]], coordinates=[2, 0])
        squin.set_detector([acc[6], acc[7]], coordinates=[3, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program(
            "accumulator_append_initialized_all_iters.stim"
        ).rstrip()
    )


def test_accumulator_prepend_initialized_all_iters():
    """Accessing measurements from every loop iteration + initial via prepend."""

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])
        squin.set_detector([acc[2], acc[3]], coordinates=[1, 0])
        squin.set_detector([acc[4], acc[5]], coordinates=[2, 0])
        squin.set_detector([acc[6], acc[7]], coordinates=[3, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program(
            "accumulator_prepend_initialized_all_iters.stim"
        ).rstrip()
    )


def test_unused_named_loop_var_becomes_repeat():
    """Loop with named but unused iteration variable should still become REPEAT."""

    @squin.kernel
    def test():
        qs = squin.qalloc(3)
        squin.broadcast.reset(qs)
        for i in range(5):
            squin.broadcast.h(qs)

    SquinToStimPass(dialects=test.dialects)(test)
    result = codegen(test)
    assert "REPEAT 5" in result
    assert "H" in result


def test_no_nested_repeat():
    """Two nested for _ in range(N) loops - only outermost becomes REPEAT."""

    @squin.kernel
    def test():
        qs = squin.qalloc(3)
        for _ in range(5):
            for _ in range(3):
                squin.broadcast.h(qs)

    SquinToStimPass(dialects=test.dialects)(test)
    result = codegen(test)
    assert result.count("REPEAT") == 1


def test_accumulator_set_observable_whole_list():
    """Regression for PR #736: set_observable(acc) where acc is a loop-grown
    accumulator. Must emit 8 record references, not 2."""

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
        squin.set_observable(acc)

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program("accumulator_set_observable_whole_list.stim").rstrip()
    )


def test_accumulator_set_detector_whole_list():
    """Sibling of the set_observable case: SetDetectorPartial has the same
    type.vars[1] vulnerability as SetObservablePartial. Must emit 8 record
    references."""

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
        squin.set_detector(acc, coordinates=[0, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program("accumulator_set_detector_whole_list.stim").rstrip()
    )
