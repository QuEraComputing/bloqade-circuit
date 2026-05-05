from typing import Any

from kirin import interp
from kirin.dialects import ilist

from bloqade.qrb.reg import QRBQubit
from bloqade.qrb.base import QRBInterpreter
from bloqade.qasm2.dialects import parallel


@parallel.dialect.register(key="qrb")
class QRBMethods(interp.MethodTable):

    @interp.impl(parallel.CZ)
    def cz(self, interp: QRBInterpreter, frame: interp.Frame, stmt: parallel.CZ):

        qargs: ilist.IList[QRBQubit, Any] = frame.get(stmt.qargs)
        ctrls: ilist.IList[QRBQubit, Any] = frame.get(stmt.ctrls)
        for qarg, ctrl in zip(qargs, ctrls):
            if qarg.is_active() and ctrl.is_active():
                interp.memory.sim_reg.mcz([ctrl.addr], qarg.addr)
        return ()

    @interp.impl(parallel.UGate)
    def ugate(
        self, interp: QRBInterpreter, frame: interp.Frame, stmt: parallel.UGate
    ):
        qargs: ilist.IList[QRBQubit, Any] = frame.get(stmt.qargs)
        theta, phi, lam = (
            frame.get(stmt.theta),
            frame.get(stmt.phi),
            frame.get(stmt.lam),
        )
        for qarg in qargs:
            if qarg.is_active():
                # qrackbind: u(theta, phi, lam, qubit) — qubit is last arg
                interp.memory.sim_reg.u(theta, phi, lam, qarg.addr)
        return ()

    @interp.impl(parallel.RZ)
    def rz(self, interp: QRBInterpreter, frame: interp.Frame, stmt: parallel.RZ):
        qargs: ilist.IList[QRBQubit, Any] = frame.get(stmt.qargs)
        phi = frame.get(stmt.theta)
        for qarg in qargs:
            if qarg.is_active():
                # qrackbind: rz(angle, qubit) — replaces pyqrack's r(3, phi, addr)
                interp.memory.sim_reg.rz(phi, qarg.addr)
        return ()
