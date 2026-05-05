from typing import Any

from kirin import interp
from kirin.dialects import ilist

from bloqade.qrb.reg import QRBQubit
from bloqade.qrb.base import QRBInterpreter
from bloqade.qasm2.dialects import glob


@glob.dialect.register(key="qrb")
class QRBMethods(interp.MethodTable):
    @interp.impl(glob.UGate)
    def ugate(self, interp: QRBInterpreter, frame: interp.Frame, stmt: glob.UGate):
        registers: ilist.IList[ilist.IList[QRBQubit, Any], Any] = frame.get(
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
                    # qrackbind: u(theta, phi, lam, qubit) — qubit is last arg
                    interp.memory.sim_reg.u(theta, phi, lam, qarg.addr)
        return ()
