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


@squin.kernel
def test_simple_linear():

    qs = squin.qalloc(4)
    m0 = squin.broadcast.measure(qs)
    squin.set_detector([m0[0], m0[1]], coordinates=[0, 0])
    m1 = squin.broadcast.measure(qs)
    squin.set_detector([m1[0], m1[1]], coordinates=[1, 1])


test_simple_linear.print()
SquinToStimPass(dialects=test_simple_linear.dialects)(test_simple_linear)
test_simple_linear.print()
print(codegen(test_simple_linear))
