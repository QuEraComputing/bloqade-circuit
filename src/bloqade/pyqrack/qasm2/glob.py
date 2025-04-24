from typing import Any

from kirin import interp
from kirin.dialects import ilist

from bloqade.pyqrack.reg import PyQrackQubit
from bloqade.pyqrack.base import PyQrackInterpreter
from bloqade.qasm2.dialects import glob


@glob.dialect.register(key="pyqrack")
class PyQrackMethods(interp.MethodTable):
    @interp.impl(glob.UGate)
    def ugate(self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: glob.UGate):
        registers: ilist.IList[ilist.IList[PyQrackQubit, Any], Any] = frame.get(
            stmt.registers
        )
        theta, phi, lam = (
            frame.get(stmt.theta),
            frame.get(stmt.phi),
            frame.get(stmt.lam),
        )

        for qreg in registers:
            for qarg in qreg:
                if qarg.is_active():
                    interp.memory.sim_reg.u(qarg.addr, theta, phi, lam)
        return ()
