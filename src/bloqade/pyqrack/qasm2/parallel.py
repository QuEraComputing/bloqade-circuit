from typing import Any

from kirin import interp
from kirin.dialects import ilist

from pyqrack.pauli import Pauli
from bloqade.pyqrack.reg import PyQrackQubit
from bloqade.pyqrack.base import PyQrackInterpreter
from bloqade.qasm2.dialects import parallel


@parallel.dialect.register(key="pyqrack")
class PyQrackMethods(interp.MethodTable):
    """PyQrack implementations of the qasm2 `parallel` statements."""

    @interp.impl(parallel.CZ)
    def cz(self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: parallel.CZ):
        """Apply CZ to each (control, target) pair."""

        qargs: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qargs)
        ctrls: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.ctrls)
        for qarg, ctrl in zip(qargs, ctrls):
            if qarg.is_active() and ctrl.is_active():
                interp.memory.sim_reg.mcz([ctrl.addr], qarg.addr)
        return ()

    @interp.impl(parallel.UGate)
    def ugate(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: parallel.UGate
    ):
        """Apply the same U(theta, phi, lam) gate to each qubit."""
        qargs: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qargs)
        theta, phi, lam = (
            frame.get(stmt.theta),
            frame.get(stmt.phi),
            frame.get(stmt.lam),
        )
        for qarg in qargs:
            if qarg.is_active():
                interp.memory.sim_reg.u(qarg.addr, theta, phi, lam)
        return ()

    @interp.impl(parallel.RZ)
    def rz(self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: parallel.RZ):
        """Apply the same RZ(theta) rotation to each qubit."""
        qargs: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qargs)
        phi = frame.get(stmt.theta)
        for qarg in qargs:
            if qarg.is_active():
                interp.memory.sim_reg.r(Pauli.PauliZ, phi, qarg.addr)
        return ()
