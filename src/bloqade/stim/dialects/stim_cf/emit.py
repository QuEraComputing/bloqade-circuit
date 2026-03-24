from kirin.interp import MethodTable, impl

from bloqade.stim.emit.stim_str import EmitStimMain, EmitStimFrame

from .stmts import Repeat
from ._dialect import dialect


@dialect.register(key="emit.stim")
class EmitStimCfMethods(MethodTable):

    @impl(Repeat)
    def emit_repeat(self, emit: EmitStimMain, frame: EmitStimFrame, stmt: Repeat):
        count: str = frame.get(stmt.count)
        frame.write_line(f"REPEAT {count} {{")
        frame._indent += 1

        for block in stmt.body.blocks:
            frame.current_block = block
            for body_stmt in block.stmts:
                frame.current_stmt = body_stmt
                res = emit.frame_eval(frame, body_stmt)
                if isinstance(res, tuple):
                    frame.set_values(body_stmt.results, res)

        frame._indent -= 1
        frame.write_line("}")

        return ()
