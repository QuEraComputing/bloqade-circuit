import sys
from typing import IO, Generic, TypeVar, cast
from contextlib import contextmanager
from dataclasses import field, dataclass

from kirin import ir, interp
from kirin.idtable import IdTable
from kirin.dialects import func
from kirin.emit.abc import EmitABC, EmitFrame

IO_t = TypeVar("IO_t", bound=IO)


@dataclass
class EmitStimFrame(EmitFrame[str], Generic[IO_t]):
    io: IO_t = cast(IO_t, sys.stdout)
    ssa: IdTable[ir.SSAValue] = field(
        default_factory=lambda: IdTable[ir.SSAValue](prefix="ssa_")
    )
    block: IdTable[ir.Block] = field(
        default_factory=lambda: IdTable[ir.Block](prefix="block_")
    )
    _indent: int = 0

    def write(self, value: str) -> None:
        self.io.write(value)

    def write_line(self, value: str) -> None:
        self.write("    " * self._indent + value + "\n")

    @contextmanager
    def indent(self):
        self._indent += 1
        try:
            yield
        finally:
            self._indent -= 1


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

    @interp.impl(func.ConstantNone)
    def emit_const_none(
        self, emit: EmitStimMain, frame: EmitStimFrame, stmt: func.ConstantNone
    ):
        frame.set(stmt.result, "")
        return (frame.get(stmt.result),)

    @interp.impl(func.Return)
    def emit_return(self, emit: EmitStimMain, frame: EmitStimFrame, stmt: func.Return):
        return ()
