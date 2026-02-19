import io
import os

from kirin import ir
from kirin.dialects import ilist

from bloqade import stim, squin
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStimPass


def codegen(mt: ir.Method):
    # method should not have any arguments!
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
    base_program = load_reference_program("repeat_on_gates_only.stim")
    assert codegen(test) == base_program.rstrip()


# Very similar to a full repetition code
# but simplified for debugging/development purposes
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
        squin.set_observable([final_ms[0]], idx=0)

    SquinToStimPass(dialects=test.dialects)(test)
    base_program = load_reference_program("rep_code_structure.stim")
    assert codegen(test) == base_program.rstrip()


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
        squin.set_detector([curr_ms[1]], coordinates=[0, 1])

        for _ in range(10):

            prev_ms = curr_ms

            squin.broadcast.cx(controls=[qs[0], qs[2]], targets=[qs[1], qs[3]])
            squin.broadcast.cx(controls=[qs[2], qs[4]], targets=[qs[1], qs[3]])

            curr_ms = squin.broadcast.measure(and_qs)

            squin.annotate.set_detector([prev_ms[0], curr_ms[0]], coordinates=[0, 0])
            squin.annotate.set_detector([prev_ms[1], curr_ms[1]], coordinates=[0, 1])

        data_ms = squin.broadcast.measure(data_qs)

        squin.set_detector([data_ms[0], data_ms[1], curr_ms[0]], coordinates=[2, 0])
        squin.set_detector([data_ms[2], data_ms[1], curr_ms[1]], coordinates=[2, 1])
        squin.set_observable([data_ms[2]], idx=0)

    SquinToStimPass(dialects=test.dialects)(test)
    base_program = load_reference_program("rep_code.stim")
    assert codegen(test) == base_program.rstrip()


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
    base_program = load_reference_program("feedforward_inside_loop.stim")
    assert codegen(test) == base_program.rstrip()


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
        squin.set_observable(measurements=[data_ms[3]], idx=0)

    SquinToStimPass(dialects=test.dialects)(test)
    base_program = load_reference_program("test_nested_unroll.stim")
    assert codegen(test) == base_program.rstrip()


def test_surface_code_memory():

    # Original auto-generated surface code has
    # a bit of a confusing numbering system for qubits, just going to organize my qubits
    # "scan-line" fashion - row by row from top to bottom.
    @squin.kernel
    def surface_code_kernel():
        qs = squin.qalloc(17)
        squin.broadcast.reset(qs)
        # prepare X stabilizer ancillas
        x_ancillas = [qs[0], qs[5], qs[11], qs[16]]
        squin.broadcast.h(x_ancillas)

        # need 4 cycles of CXs to get everything initially entangled
        # (yes I did this by hand, checking against the stim "timeslice-svg" output)
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

        # apply H again to X ancillas
        squin.broadcast.h(x_ancillas)

        # Measure and reset ALL ancilla qubits
        ancilla_qs = [qs[0], qs[4], qs[5], qs[6], qs[10], qs[11], qs[12], qs[16]]
        curr_ancilla_ms = squin.broadcast.measure(qubits=ancilla_qs)
        squin.broadcast.reset(ancilla_qs)

        # put detectors on the Z ancillas
        z_ancillas_ms = [
            curr_ancilla_ms[1],
            curr_ancilla_ms[3],
            curr_ancilla_ms[4],
            curr_ancilla_ms[6],
        ]
        for i in range(len(z_ancillas_ms)):
            squin.set_detector(measurements=[z_ancillas_ms[i]], coordinates=[0, 0])

        # begin the REPEAT
        for _ in range(100):
            prev_ancilla_ms = curr_ancilla_ms
            squin.broadcast.h(x_ancillas)
            squin.broadcast.cx(controls=cx_cycle_1_ctrls, targets=cx_cycle_1_targs)
            squin.broadcast.cx(controls=cx_cycle_2_ctrls, targets=cx_cycle_2_targs)
            squin.broadcast.cx(controls=cx_cycle_3_ctrls, targets=cx_cycle_3_targs)
            squin.broadcast.cx(controls=cx_cycle_4_ctrls, targets=cx_cycle_4_targs)
            curr_ancilla_ms = squin.broadcast.measure(qubits=ancilla_qs)
            squin.broadcast.reset(ancilla_qs)

            # set detectors, assert parity between previous and current measurements
            for i in range(len(curr_ancilla_ms)):
                squin.set_detector(
                    measurements=[curr_ancilla_ms[i], prev_ancilla_ms[i]],
                    coordinates=[0, 0],
                )

        # measure out the data qubits
        data_qs = [qs[1], qs[2], qs[3], qs[7], qs[8], qs[9], qs[13], qs[14], qs[15]]
        data_ms = squin.broadcast.measure(qubits=data_qs)

        # set up the last round of detectors before logical observable
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

        squin.set_observable(measurements=[data_ms[0], data_ms[1], data_ms[2]], idx=0)

    SquinToStimPass(dialects=surface_code_kernel.dialects)(surface_code_kernel)
    base_program = load_reference_program("surface_code_memory.stim")
    assert codegen(surface_code_kernel) == base_program.rstrip()


def test_color_code_memory_init():

    @squin.kernel
    def color_code_kernel_init():

        # Imitates the C_XYZ operation in Stim
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
    base_program = load_reference_program("color_code_init.stim")
    assert codegen(color_code_kernel_init) == base_program.rstrip()


test_color_code_memory_init()


def test_accumulator_append_empty_init():

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(squin.qalloc(0))
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    base_program = load_reference_program("accumulator_append_empty_init.stim")
    assert codegen(test) == base_program.rstrip()


def test_accumulator_prepend_empty_init():

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(squin.qalloc(0))
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    base_program = load_reference_program("accumulator_prepend_empty_init.stim")
    assert codegen(test) == base_program.rstrip()


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
    base_program = load_reference_program("accumulator_append_initialized.stim")
    assert codegen(test) == base_program.rstrip()


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
    base_program = load_reference_program("accumulator_prepend_initialized.stim")
    assert codegen(test) == base_program.rstrip()
