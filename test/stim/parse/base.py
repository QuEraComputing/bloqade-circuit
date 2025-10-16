from kirin import ir
from io import StringIO
from bloqade.stim.emit import EmitStimMain
from bloqade import stim

buf = StringIO()
emit = EmitStimMain(stim.main, io=buf)


def codegen(mt: ir.Method):
    # method should not have any arguments!
    emit.initialize()
    emit.run(node=mt)
    return buf.getvalue().strip()
