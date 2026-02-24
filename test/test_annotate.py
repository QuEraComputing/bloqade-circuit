import io

from kirin import ir

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


def test_annotate():

    @squin.kernel
    def test():
        qs = squin.qalloc(4)
        ms = squin.broadcast.measure(qs)
        squin.set_detector([ms[0], ms[1], ms[2]], coordinates=(0, 0))
        squin.set_observable([ms[3]])

    SquinToStimPass(dialects=test.dialects)(test)
    codegen_output = codegen(test)
    expected_output = (
        "MZ(0.00000000) 0 1 2 3\n"
        "DETECTOR(0, 0) rec[-4] rec[-3] rec[-2]\n"
        "OBSERVABLE_INCLUDE(0) rec[-1]"
    )
    assert codegen_output == expected_output


def test_set_observable_with_multiple_idx():

    @squin.kernel
    def test():
        qs = squin.qalloc(4)
        ms = squin.broadcast.measure(qs)
        squin.set_observable([ms[0], ms[1]])
        squin.set_observable([ms[2]])
        squin.set_observable([ms[3]])

    SquinToStimPass(dialects=test.dialects)(test)
    codegen_output = codegen(test)
    expected_output = (
        "MZ(0.00000000) 0 1 2 3\n"
        "OBSERVABLE_INCLUDE(0) rec[-4] rec[-3]\n"
        "OBSERVABLE_INCLUDE(1) rec[-2]\n"
        "OBSERVABLE_INCLUDE(2) rec[-1]"
    )
    assert codegen_output == expected_output
