import math
from typing import Any

from kirin import interp
from kirin.dialects import ilist

from bloqade.qrb import QRBQubit
from bloqade.qrb.base import QRBInterpreter
from bloqade.native.dialects.gate import stmts


@stmts.dialect.register(key="qrb")
class NativeMethods(interp.MethodTable):

    @interp.impl(stmts.CZ)
    def cz(self, _interp: QRBInterpreter, frame: interp.Frame, stmt: stmts.CZ):
        controls = frame.get_casted(stmt.controls, ilist.IList[QRBQubit, Any])
        targets = frame.get_casted(stmt.targets, ilist.IList[QRBQubit, Any])

        for ctrl, trgt in zip(controls, targets):
            if ctrl.is_active() and trgt.is_active():
                ctrl.sim_reg.mcz([ctrl.addr], trgt.addr)

        return ()

    @interp.impl(stmts.R)
    def r(self, _interp: QRBInterpreter, frame: interp.Frame, stmt: stmts.R):
        qubits = frame.get_casted(stmt.qubits, ilist.IList[QRBQubit, Any])
        rotation_angle = 2 * math.pi * frame.get_casted(stmt.rotation_angle, float)
        axis_angle = 2 * math.pi * frame.get_casted(stmt.axis_angle, float)

        # Decompose R(rotation_angle, axis_angle) as Rz(-axis) Rx(rotation) Rz(axis)
        # qrackbind: rz(angle, qubit), rx(angle, qubit) — note arg order vs pyqrack's r(axis, angle, qubit)
        for qubit in qubits:
            if qubit.is_active():
                qubit.sim_reg.rz(-axis_angle, qubit.addr)
                qubit.sim_reg.rx(rotation_angle, qubit.addr)
                qubit.sim_reg.rz(axis_angle, qubit.addr)

        return ()

    @interp.impl(stmts.Rz)
    def rz(self, _interp: QRBInterpreter, frame: interp.Frame, stmt: stmts.Rz):
        qubits = frame.get_casted(stmt.qubits, ilist.IList[QRBQubit, Any])
        rotation_angle = 2 * math.pi * frame.get_casted(stmt.rotation_angle, float)

        # qrackbind: rz(angle, qubit) — note arg order vs pyqrack's r(Pauli.PauliZ, angle, qubit)
        for qubit in qubits:
            if qubit.is_active():
                qubit.sim_reg.rz(rotation_angle, qubit.addr)

        return ()
