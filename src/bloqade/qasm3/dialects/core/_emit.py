"""Emit method table for the qasm3.core dialect."""

from kirin import interp

from bloqade.qasm3.emit.main import EmitQASM3Main, EmitQASM3Frame

from . import stmts
from ._dialect import dialect


@dialect.register(key="emit.qasm3.main")
class Core(interp.MethodTable):

    @interp.impl(stmts.QRegNew)
    def emit_qreg_new(
        self, emit: EmitQASM3Main, frame: EmitQASM3Frame, stmt: stmts.QRegNew
    ):
        size = frame.get(stmt.n_qubits)
        name = emit.ssa_id[stmt.result]
        frame.body.append(f"qubit[{size}] {name};")
        return (name,)

    @interp.impl(stmts.BitRegNew)
    def emit_bitreg_new(
        self, emit: EmitQASM3Main, frame: EmitQASM3Frame, stmt: stmts.BitRegNew
    ):
        size = frame.get(stmt.n_bits)
        name = emit.ssa_id[stmt.result]
        frame.body.append(f"bit[{size}] {name};")
        return (name,)

    @interp.impl(stmts.QRegGet)
    def emit_qreg_get(
        self, emit: EmitQASM3Main, frame: EmitQASM3Frame, stmt: stmts.QRegGet
    ):
        reg_name = frame.get(stmt.reg)
        idx = frame.get(stmt.idx)
        return (f"{reg_name}[{idx}]",)

    @interp.impl(stmts.BitRegGet)
    def emit_bitreg_get(
        self, emit: EmitQASM3Main, frame: EmitQASM3Frame, stmt: stmts.BitRegGet
    ):
        reg_name = frame.get(stmt.reg)
        idx = frame.get(stmt.idx)
        return (f"{reg_name}[{idx}]",)

    @interp.impl(stmts.Measure)
    def emit_measure(
        self, emit: EmitQASM3Main, frame: EmitQASM3Frame, stmt: stmts.Measure
    ):
        qarg = frame.get(stmt.qarg)
        carg = frame.get(stmt.carg)
        frame.body.append(f"{carg} = measure {qarg};")
        return ()

    @interp.impl(stmts.Reset)
    def emit_reset(
        self, emit: EmitQASM3Main, frame: EmitQASM3Frame, stmt: stmts.Reset
    ):
        qarg = frame.get(stmt.qarg)
        frame.body.append(f"reset {qarg};")
        return ()

    @interp.impl(stmts.Barrier)
    def emit_barrier(
        self, emit: EmitQASM3Main, frame: EmitQASM3Frame, stmt: stmts.Barrier
    ):
        qargs = ", ".join(str(frame.get(q)) for q in stmt.qargs)
        frame.body.append(f"barrier {qargs};")
        return ()
