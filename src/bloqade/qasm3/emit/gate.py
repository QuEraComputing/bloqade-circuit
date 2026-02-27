"""Gate-level QASM3 emitter for custom gate definitions."""

from dataclasses import field, dataclass

from kirin import ir, interp
from kirin.dialects import func
from kirin.ir.dialect import Dialect as Dialect
from typing_extensions import Self

from bloqade.qasm3.types import QubitType
from bloqade.qasm3.dialects.expr.stmts import GateFunction

from .base import EmitQASM3Base, EmitQASM3Frame


def _default_dialect_group():
    from bloqade.qasm3.groups import gate

    return gate


@dataclass
class EmitQASM3Gate(EmitQASM3Base):
    keys = ("emit.qasm3.gate",)
    dialects: ir.DialectGroup = field(default_factory=_default_dialect_group)

    def initialize(self) -> Self:
        super().initialize()
        return self


@func.dialect.register(key="emit.qasm3.gate")
class Func(interp.MethodTable):

    @interp.impl(func.Return)
    def emit_return(
        self, emit: EmitQASM3Gate, frame: EmitQASM3Frame, stmt: func.Return
    ):
        return ()

    @interp.impl(func.ConstantNone)
    def emit_constant_none(
        self, emit: EmitQASM3Gate, frame: EmitQASM3Frame, stmt: func.ConstantNone
    ):
        return (None,)

    @interp.impl(GateFunction)
    def emit_gate_func(
        self, emit: EmitQASM3Gate, frame: EmitQASM3Frame, stmt: GateFunction
    ):
        cparams: list[str] = []
        qparams: list[str] = []
        entry_args = stmt.body.blocks[0].args
        user_args = entry_args[1:] if len(entry_args) > 0 else []

        args: list[str] = []
        for arg in user_args:
            name = arg.name or f"_arg{len(args)}"
            args.append(name)
            if arg.type.is_subseteq(QubitType):
                qparams.append(name)
            else:
                cparams.append(name)

        # Set up SSA mappings for gate body parameters
        frame.worklist.append(interp.Successor(stmt.body.blocks[0], *args))
        if len(entry_args) > 0:
            frame.set(entry_args[0], stmt.sym_name or "gate")

        while (succ := frame.worklist.pop()) is not None:
            frame.set_values(succ.block.args[1:], succ.block_args)
            block_header = emit.emit_block(frame, succ.block)
            frame.block_ref[succ.block] = block_header

        # Build the gate definition string
        gate_name = stmt.sym_name
        if cparams:
            header = f"gate {gate_name}({', '.join(cparams)}) {', '.join(qparams)}"
        else:
            header = f"gate {gate_name} {', '.join(qparams)}"

        body_lines = [f"  {line}" for line in frame.body]
        gate_block = header + " {\n" + "\n".join(body_lines) + "\n}\n"
        emit.output = gate_block
        return ()
