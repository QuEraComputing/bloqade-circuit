"""Emit method table for the qasm3.expr dialect."""

from kirin import interp

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

    @interp.impl(stmts.ConstBool)
    def emit_const_bool(
        self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.ConstBool
    ):
        return ("true" if stmt.value else "false",)

    @interp.impl(stmts.ConstComplex)
    def emit_const_complex(
        self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.ConstComplex
    ):
        v = stmt.value
        if v.real == 0:
            return (f"{emit.format_float(v.imag)}im",)
        return (f"({emit.format_float(v.real)} + {emit.format_float(v.imag)}im)",)

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

    @interp.impl(stmts.Pow)
    def emit_pow(self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.Pow):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)
        return (f"({lhs} ** {rhs})",)

    @interp.impl(stmts.Mod)
    def emit_mod(self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.Mod):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)
        return (f"({lhs} % {rhs})",)

    @interp.impl(stmts.BitNot)
    def emit_bitnot(
        self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.BitNot
    ):
        operand = frame.get(stmt.value)
        return (f"~{operand}",)

    @interp.impl(stmts.Sin)
    def emit_sin(self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.Sin):
        arg = frame.get(stmt.value)
        return (f"sin({arg})",)

    @interp.impl(stmts.Cos)
    def emit_cos(self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.Cos):
        arg = frame.get(stmt.value)
        return (f"cos({arg})",)

    @interp.impl(stmts.Tan)
    def emit_tan(self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.Tan):
        arg = frame.get(stmt.value)
        return (f"tan({arg})",)

    @interp.impl(stmts.Exp)
    def emit_exp(self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.Exp):
        arg = frame.get(stmt.value)
        return (f"exp({arg})",)

    @interp.impl(stmts.Log)
    def emit_log(self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.Log):
        arg = frame.get(stmt.value)
        return (f"log({arg})",)

    @interp.impl(stmts.Sqrt)
    def emit_sqrt(self, emit: EmitQASM3Base, frame: EmitQASM3Frame, stmt: stmts.Sqrt):
        arg = frame.get(stmt.value)
        return (f"sqrt({arg})",)
