import math
from typing import Any

from kirin import interp
from kirin.dialects import ilist

from pyqrack import Pauli
from bloqade.pyqrack import PyQrackQubit
from bloqade.pyqrack.base import PyQrackInterpreter
from bloqade.native.dialects import gates


@gates.dialect.register(key="pyqrack")
class NativeMethods(interp.MethodTable):

    @interp.impl(gates.CZ)
    def cz(self, _interp: PyQrackInterpreter, frame: interp.Frame, stmt: gates.CZ):
        ctrls = frame.get_casted(stmt.ctrls, ilist.IList[PyQrackQubit, Any])
        qargs = frame.get_casted(stmt.qargs, ilist.IList[PyQrackQubit, Any])

        for ctrl, qarg in zip(ctrls, qargs):
            if ctrl.is_active() and qarg.is_active():
                ctrl.sim_reg.mcz([ctrl.addr], qarg.addr)

        return ()

    @interp.impl(gates.R)
    def r(self, _interp: PyQrackInterpreter, frame: interp.Frame, stmt: gates.R):
        inputs = frame.get_casted(stmt.inputs, ilist.IList[PyQrackQubit, Any])
        rotation_angle = 2 * math.pi * frame.get_casted(stmt.rotation_angle, float)
        axis_angle = 2 * math.pi * frame.get_casted(stmt.axis_angle, float)
        for qubit in inputs:
            if qubit.is_active():
                qubit.sim_reg.r(Pauli.PauliZ, axis_angle, qubit.addr)
                qubit.sim_reg.r(Pauli.PauliX, rotation_angle, qubit.addr)
                qubit.sim_reg.r(Pauli.PauliZ, -axis_angle, qubit.addr)

        return ()

    @interp.impl(gates.Rz)
    def rz(self, _interp: PyQrackInterpreter, frame: interp.Frame, stmt: gates.Rz):
        inputs = frame.get_casted(stmt.inputs, ilist.IList[PyQrackQubit, Any])
        rotation_angle = 2 * math.pi * frame.get_casted(stmt.rotation_angle, float)

        for qubit in inputs:
            if qubit.is_active():
                qubit.sim_reg.r(Pauli.PauliZ, rotation_angle, qubit.addr)

        return ()
