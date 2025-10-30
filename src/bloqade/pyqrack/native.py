import math
from typing import Any

from kirin import interp
from kirin.dialects import ilist

from pyqrack import Pauli
from bloqade.pyqrack import PyQrackQubit
from bloqade.pyqrack.base import PyQrackInterpreter
from bloqade.native.dialects.gate import stmts


@stmts.dialect.register(key="pyqrack")
class NativeMethods(interp.MethodTable):

    @interp.impl(stmts.CZ)
    def cz(self, _interp: PyQrackInterpreter, frame: interp.Frame, stmt: stmts.CZ):
        controls = frame.get_casted(stmt.controls, ilist.IList[PyQrackQubit, Any])
        targets = frame.get_casted(stmt.targets, ilist.IList[PyQrackQubit, Any])

        for ctrl, trgt in zip(controls, targets):
            if ctrl.is_active() and trgt.is_active():
                ctrl.sim_reg.mcz([ctrl.addr], trgt.addr)

        return ()

    @interp.impl(stmts.R)
    def r(self, _interp: PyQrackInterpreter, frame: interp.Frame, stmt: stmts.R):
        qubits = frame.get_casted(stmt.qubits, ilist.IList[PyQrackQubit, Any])
        rotation_angle = 2 * math.pi * frame.get_casted(stmt.rotation_angle, float)
        axis_angle = 2 * math.pi * frame.get_casted(stmt.axis_angle, float)
        for qubit in qubits:
            if qubit.is_active():
                qubit.sim_reg.r(Pauli.PauliZ, axis_angle, qubit.addr)
                qubit.sim_reg.r(Pauli.PauliX, rotation_angle, qubit.addr)
                qubit.sim_reg.r(Pauli.PauliZ, -axis_angle, qubit.addr)

        return ()

    @interp.impl(stmts.Rz)
    def rz(self, _interp: PyQrackInterpreter, frame: interp.Frame, stmt: stmts.Rz):
        qubits = frame.get_casted(stmt.qubits, ilist.IList[PyQrackQubit, Any])
        rotation_angle = 2 * math.pi * frame.get_casted(stmt.rotation_angle, float)

        for qubit in qubits:
            if qubit.is_active():
                qubit.sim_reg.r(Pauli.PauliZ, rotation_angle, qubit.addr)

        return ()
