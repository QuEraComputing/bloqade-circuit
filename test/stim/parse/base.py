from io import StringIO

from kirin import ir

from bloqade import stim
from bloqade.stim.emit import EmitStimMain

buf = StringIO()
emit = EmitStimMain(stim.main, io=buf)


def codegen(mt: ir.Method):
    # method should not have any arguments!
    emit.initialize()
    emit.run(node=mt)
    return buf.getvalue().strip()
