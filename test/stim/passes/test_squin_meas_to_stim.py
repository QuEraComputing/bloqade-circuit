import io
import os

from kirin import ir
from kirin.dialects.ilist import IList

from bloqade import stim, squin as sq
from bloqade.types import MeasurementResult
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
    """Load stim file."""
    path = os.path.join(
        os.path.dirname(__file__), "stim_reference_programs", "qubit", filename
    )
    with open(path, "r") as f:
        return f.read().strip()


def test_cond_on_measurement():

    @sq.kernel
    def main():
        n_qubits = 4
        q = sq.qalloc(n_qubits)

        ms = sq.broadcast.measure(q)

        if ms[0]:
            sq.z(q[0])
            sq.broadcast.x([q[1], q[2], q[3]])
            sq.broadcast.z(q)

        if ms[1]:
            sq.x(q[0])
            sq.y(q[1])

        sq.broadcast.measure(q)

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_reference_program("simple_if_rewrite.stim")

    assert base_stim_prog == codegen(main)


def test_alias_with_measure_list():

    @sq.kernel
    def main():

        q = sq.qalloc(4)
        ms = sq.broadcast.measure(q)
        new_ms = ms

        if new_ms[0]:
            sq.z(q[0])

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_reference_program("alias_with_measure_list.stim")

    assert base_stim_prog == codegen(main)


def test_record_index_order():

    @sq.kernel
    def main():
        n_qubits = 4
        q = sq.qalloc(n_qubits)

        ms0 = sq.broadcast.measure(q)

        if ms0[0]:  # should be rec[-4]
            sq.z(q[0])

        # another measurement
        ms1 = sq.broadcast.measure(q)

        if ms1[0]:  # should be rec[-4]
            sq.x(q[0])

        # second round of measurement
        ms2 = sq.broadcast.measure(q)  # noqa: F841

        # try accessing measurements from the very first round
        ## There are now 12 total measurements, ms0[0]
        ## is the oldest measurement in the entire program
        if ms0[0]:
            sq.y(q[1])

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_reference_program("record_index_order.stim")

    assert base_stim_prog == codegen(main)


def test_complex_intermediate_storage_of_measurements():

    @sq.kernel
    def main():
        n_qubits = 4
        q = sq.qalloc(n_qubits)

        ms0 = sq.broadcast.measure(q)

        if ms0[0]:
            sq.z(q[0])

        ms1 = sq.broadcast.measure(q)

        if ms1[0]:
            sq.x(q[1])

        # another measurement
        ms2 = sq.broadcast.measure(q)

        if ms2[0]:
            sq.y(q[2])

        # Intentionally obnoxious mix of measurements
        mix = [ms0[0], ms1[2], ms2[3]]
        mix_again = (mix[2], mix[0])

        if mix_again[0]:
            sq.z(q[3])

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_reference_program("complex_storage_index_order.stim")

    assert base_stim_prog == codegen(main)


def test_addition_assignment_on_measures_in_list():

    @sq.kernel(fold=False)
    def main():
        q = sq.qalloc(2)
        results = []

        result: MeasurementResult = sq.qubit.measure(q[0])
        results += [result]
        result: MeasurementResult = sq.qubit.measure(q[1])
        results += [result]

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_reference_program("addition_assignment_measure.stim")

    assert base_stim_prog == codegen(main)


def test_measure_desugar():

    pairs = IList([0, 1, 2, 3])

    @sq.kernel
    def main():
        q = sq.qalloc(10)
        sq.qubit.measure(q[pairs[0]])
        for i in range(1):
            sq.qubit.measure(q[0])
            sq.qubit.measure(q[i])
            sq.qubit.measure(q[pairs[0]])
            sq.qubit.measure(q[pairs[i]])

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_reference_program("measure_desugar.stim")

    assert base_stim_prog == codegen(main)
