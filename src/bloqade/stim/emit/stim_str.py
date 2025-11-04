import sys
from typing import IO, Generic, TypeVar, cast
from dataclasses import dataclass

from kirin import ir, interp
from kirin.dialects import func
from kirin.emit.abc import EmitABC, EmitFrame

IO_t = TypeVar("IO_t", bound=IO)


@dataclass
class EmitStimFrame(EmitFrame[str], Generic[IO_t]):
    io: IO_t = cast(IO_t, sys.stdout)

    def write(self, value: str) -> None:
        self.io.write(value)

    def write_line(self, value: str) -> None:
        self.write("    " * self._indent + value + "\n")


@dataclass
class EmitStimMain(EmitABC[EmitStimFrame, str], Generic[IO_t]):
    io: IO_t = cast(IO_t, sys.stdout)
    keys = ("emit.stim",)
    void = ""
    correlation_identifier_offset: int = 0

    def initialize(self) -> "EmitStimMain":
        super().initialize()
        self.correlated_error_count = self.correlation_identifier_offset
        return self

    def initialize_frame(
        self, node: ir.Statement, *, has_parent_access: bool = False
    ) -> EmitStimFrame:
        return EmitStimFrame(node, self.io, has_parent_access=has_parent_access)

    def frame_call(
        self, frame: EmitStimFrame, node: ir.Statement, *args: str, **kwargs: str
    ) -> str:
        return f"{args[0]}({', '.join(args[1:])})"

    def get_attribute(self, frame: EmitStimFrame, node: ir.Attribute) -> str:
        method = self.registry.get(interp.Signature(type(node)))
        if method is None:
            raise ValueError(f"Method not found for node: {node}")
        return method(self, frame, node)

    def reset(self):
        self.io.truncate(0)
        self.io.seek(0)

    def eval_fallback(self, frame: EmitStimFrame, node: ir.Statement) -> tuple:
        return tuple("" for _ in range(len(node.results)))


@func.dialect.register(key="emit.stim")
class FuncEmit(interp.MethodTable):
    @interp.impl(func.Function)
    def emit_func(self, emit: EmitStimMain, frame: EmitStimFrame, stmt: func.Function):
        for block in stmt.body.blocks:
            frame.current_block = block
            for stmt_ in block.stmts:
                frame.current_stmt = stmt_
                res = emit.frame_eval(frame, stmt_)
                if isinstance(res, tuple):
                    frame.set_values(stmt_.results, res)

        return ()
