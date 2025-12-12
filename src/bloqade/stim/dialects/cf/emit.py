from kirin.interp import MethodTable, impl

from bloqade.stim.emit.stim_str import EmitStimMain, EmitStimFrame

from . import stmts
from ._dialect import dialect


@dialect.register(key="emit.stim")
class EmitStimCfMethods(MethodTable):

    @impl(stmts.REPEAT)
    def repeat(self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.REPEAT):

        count = frame.get(stmt.count)
        frame.write_line(f"REPEAT {count} {{")
        with frame.indent():

            # Assume single block in REPEAT
            for inner_stmt in stmt.body.blocks[0].stmts:
                inner_stmt_results = emit.frame_eval(frame, inner_stmt)

                match inner_stmt_results:
                    case tuple():
                        frame.set_values(inner_stmt._results, inner_stmt_results)
                    case _:
                        continue

        frame.write_line("}")

        return ()
