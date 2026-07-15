"""Emit method table for the qasm3.uop dialect."""

from kirin import interp

from bloqade.qasm3.emit.gate import EmitQASM3Gate, EmitQASM3Frame

from . import stmts
from ._dialect import dialect


@dialect.register(key="emit.qasm3.gate")
class UOp(interp.MethodTable):

    @interp.impl(stmts.UGate)
    def emit_ugate(self, emit: EmitQASM3Gate, frame: EmitQASM3Frame, stmt: stmts.UGate):
        theta = frame.get(stmt.theta)
        phi = frame.get(stmt.phi)
        lam = frame.get(stmt.lam)
        qarg = frame.get(stmt.qarg)
        frame.body.append(f"U({theta}, {phi}, {lam}) {qarg};")
        return ()

    @interp.impl(stmts.H)
    @interp.impl(stmts.X)
    @interp.impl(stmts.Y)
    @interp.impl(stmts.Z)
    @interp.impl(stmts.S)
    @interp.impl(stmts.T)
    def emit_single_qubit_gate(
        self, emit: EmitQASM3Gate, frame: EmitQASM3Frame, stmt: stmts.SingleQubitGate
    ):
        qarg = frame.get(stmt.qarg)
        frame.body.append(f"{stmt.name} {qarg};")
        return ()

    @interp.impl(stmts.RX)
    @interp.impl(stmts.RY)
    @interp.impl(stmts.RZ)
    def emit_rotation_gate(
        self, emit: EmitQASM3Gate, frame: EmitQASM3Frame, stmt: stmts.RotationGate
    ):
        theta = frame.get(stmt.theta)
        qarg = frame.get(stmt.qarg)
        frame.body.append(f"{stmt.name}({theta}) {qarg};")
        return ()

    @interp.impl(stmts.CX)
    @interp.impl(stmts.CY)
    @interp.impl(stmts.CZ)
    def emit_two_qubit_gate(
        self, emit: EmitQASM3Gate, frame: EmitQASM3Frame, stmt: stmts.TwoQubitCtrlGate
    ):
        ctrl = frame.get(stmt.ctrl)
        qarg = frame.get(stmt.qarg)
        frame.body.append(f"{stmt.name} {ctrl}, {qarg};")
        return ()
