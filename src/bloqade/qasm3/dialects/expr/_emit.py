"""Emit method table for the qasm3.expr dialect."""

from kirin import interp
from kirin.dialects import py

from bloqade.qasm3.emit.base import EmitQASM3Base, EmitQASM3Frame

from . import stmts
from ._dialect import dialect


@dialect.register(key="emit.qasm3.gate")
class EmitExpr(interp.MethodTable):

    @interp.impl(stmts.ConstInt)
    def emit_const_int(
        self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.ConstInt
    ):
        return (str(stmt.value),)

    @interp.impl(stmts.ConstFloat)
    def emit_const_float(
        self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.ConstFloat
    ):
        return (emit.format_float(stmt.value),)

    @interp.impl(stmts.ConstPI)
    def emit_const_pi(
        self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.ConstPI
    ):
        return ("pi",)

    @interp.impl(stmts.Neg)
    def emit_neg(self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.Neg):
        operand = frame.get(stmt.value)
        return (f"-{operand}",)

    @interp.impl(stmts.Add)
    def emit_add(self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.Add):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)
        return (f"({lhs} + {rhs})",)

    @interp.impl(stmts.Sub)
    def emit_sub(self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.Sub):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)
        return (f"({lhs} - {rhs})",)

    @interp.impl(stmts.Mul)
    def emit_mul(self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.Mul):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)
        return (f"({lhs} * {rhs})",)

    @interp.impl(stmts.Div)
    def emit_div(self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.Div):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)
        return (f"({lhs} / {rhs})",)

    @interp.impl(stmts.GateFunction)
    def emit_gate_func(
        self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.GateFunction
    ):
        # GateFunction definitions are handled by the gate emitter;
        # in the main emitter context, just skip.
        return ()


@py.constant.dialect.register(key="emit.qasm3.gate")
class Constant(interp.MethodTable):

    @interp.impl(py.Constant)
    def emit_constant(
        self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: py.Constant
    ):
        value = stmt.value.unwrap() if hasattr(stmt.value, "unwrap") else stmt.value
        if isinstance(value, float):
            return (emit.format_float(value),)
        return (str(value),)


@py.indexing.dialect.register(key="emit.qasm3.gate")
class Indexing(interp.MethodTable):

    @interp.impl(py.indexing.GetItem)
    def emit_getitem(
        self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: py.indexing.GetItem
    ):
        obj = frame.get(stmt.obj)
        idx = frame.get(stmt.index)
        return (f"{obj}[{idx}]",)
