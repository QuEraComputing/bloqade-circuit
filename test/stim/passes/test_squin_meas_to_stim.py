import os

from kirin import ir

from bloqade import squin
from bloqade.squin import op, qubit
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStimPass


def codegen(mt: ir.Method):
    # method should not have any arguments!
    emit = EmitStimMain()
    emit.initialize()
    emit.run(mt=mt, args=())
    return emit.get_output()


def load_reference_program(filename):
    path = os.path.join(os.path.dirname(__file__), "stim_reference_programs", filename)
    with open(path, "r") as f:
        return f.read()


def test_cond_on_measurement():

    @squin.kernel
    def main():
        n_qubits = 4
        q = qubit.new(n_qubits)

        ms = qubit.measure(q)

        if ms[0]:
            qubit.apply(op.z(), q[0])
            qubit.broadcast(op.x(), [q[1], q[2], q[3]])
            qubit.broadcast(op.z(), q)

        if ms[1]:
            qubit.apply(op.x(), q[0])
            qubit.apply(op.y(), q[1])

        qubit.measure(q)

    SquinToStimPass(main.dialects)(main)

    main.print()

    base_stim_prog = load_reference_program("simple_if_rewrite.txt")

    assert base_stim_prog.rstrip() == codegen(main)


def test_alias_with_measure_list():

    @squin.kernel
    def main():

        q = qubit.new(4)
        ms = qubit.measure(q)
        new_ms = ms

        if new_ms[0]:
            qubit.apply(op.z(), q[0])

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_reference_program("alias_with_measure_list.stim")

    assert base_stim_prog.rstrip() == codegen(main)
