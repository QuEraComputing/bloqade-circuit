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

    path = os.path.join(
        os.path.dirname(__file__), "stim_reference_programs", "simple_if_rewrite.txt"
    )
    with open(path, "r") as f:
        base_stim_prog = f.read()

    assert base_stim_prog.rstrip() == codegen(main)
