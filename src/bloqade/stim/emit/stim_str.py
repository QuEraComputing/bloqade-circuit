from typing import IO, TypeVar, Generic
from dataclasses import field, dataclass
from contextlib import contextmanager

from kirin import ir, interp
from kirin.idtable import IdTable
from kirin.worklist import WorkList
from kirin.emit.abc import EmitABC, EmitFrame
from kirin.dialects import func

IO_t = TypeVar("IO_t", bound=IO)


@dataclass
class EmitStimFrame(EmitFrame[str], Generic[IO_t]):
    io: IO_t
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
    io: IO_t
    keys = ("emit.stim",)
    void = ""
    callables: IdTable[ir.Statement] = field(init=False)
    callable_to_emit: WorkList[ir.Statement] = field(init=False)

    def initialize(self) -> "EmitStimMain":
        super().initialize()
        self.callables: IdTable[ir.Statement] = IdTable(prefix="fn_")
        self.callable_to_emit: WorkList[ir.Statement] = WorkList()
        return self

    def initialize_frame(
        self, node: ir.Statement, *, has_parent_access: bool = False
    ) -> EmitStimFrame:
        return EmitStimFrame(node, self.io, has_parent_access=has_parent_access)

    def run(self, node: ir.Method | ir.Statement):
        try:
            self.io.truncate(0)
            self.io.seek(0)
        except Exception:
            # not all IOs support truncate/seek (e.g. sys.stdout) — ignore silently
            pass

        if isinstance(node, ir.Method):
            node = node.code

        with self.eval_context():
            self.callables.add(node)
            self.callable_to_emit.append(node)
            while self.callable_to_emit:
                callable = self.callable_to_emit.pop()
                if callable is None:
                    break
                self.eval(callable)
                self.io.flush()
        return

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
    def emit_return(
        self, emit: EmitStimMain, frame: EmitStimFrame, stmt: func.Return
    ):
        return ()