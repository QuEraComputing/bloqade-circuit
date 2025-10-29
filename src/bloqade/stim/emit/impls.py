from kirin.emit import EmitStrFrame
from kirin.interp import MethodTable, impl
from kirin.dialects.debug import Info, dialect

from bloqade.stim.emit.stim_str import EmitStimMain


@dialect.register(key="emit.stim")
class EmitStimDebugMethods(MethodTable):

    @impl(Info)
    def info(self, emit: EmitStimMain, frame: EmitStrFrame, stmt: Info):

        msg: str = frame.get(stmt.msg)
        emit.writeln(frame, f"# {msg}")

        return ()
