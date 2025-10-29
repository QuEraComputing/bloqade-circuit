from kirin.interp import MethodTable, impl
from kirin.dialects.debug import Info, dialect

from bloqade.stim.emit.stim_str import EmitStimMain, EmitStimFrame


@dialect.register(key="emit.stim")
class EmitStimDebugMethods(MethodTable):

    @impl(Info)
    def info(self, emit: EmitStimMain, frame: EmitStimFrame, stmt: Info):

        msg: str = frame.get(stmt.msg)
        frame.write_line(f"# {msg}")

        return ()
