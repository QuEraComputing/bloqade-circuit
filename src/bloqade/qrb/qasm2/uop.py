import math

from kirin import interp

from bloqade.qrb.reg import QRBQubit
from bloqade.qasm2.dialects import uop


@uop.dialect.register(key="qrb")
class QRBMethods(interp.MethodTable):
    # qrackbind uses sdg/tdg (same as QASM names); pyqrack used adjs/adjt
    GATE_TO_METHOD = {
        "x": "x", "y": "y", "z": "z", "h": "h", "s": "s", "t": "t",
        "cx": "mcx", "CX": "mcx", "cz": "mcz", "cy": "mcy",
        "sdag": "sdg", "sdg": "sdg", "tdag": "tdg", "tdg": "tdg",
    }

    @interp.impl(uop.Barrier)
    def barrier(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.Barrier):
        return ()

    @interp.impl(uop.X)
    @interp.impl(uop.Y)
    @interp.impl(uop.Z)
    @interp.impl(uop.H)
    @interp.impl(uop.S)
    @interp.impl(uop.Sdag)
    @interp.impl(uop.T)
    @interp.impl(uop.Tdag)
    def single_qubit_gate(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.SingleQubitGate):
        qarg: QRBQubit = frame.get(stmt.qarg)
        if qarg.is_active():
            getattr(qarg.sim_reg, self.GATE_TO_METHOD[stmt.name])(qarg.addr)
        return ()

    @interp.impl(uop.UGate)
    def ugate(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.UGate):
        qarg: QRBQubit = frame.get(stmt.qarg)
        if qarg.is_active():
            # qrackbind: u(theta, phi, lam, qubit) -- qubit is last arg
            qarg.sim_reg.u(frame.get(stmt.theta), frame.get(stmt.phi), frame.get(stmt.lam), qarg.addr)
        return ()

    @interp.impl(uop.Id)
    def id(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.Id):
        return ()

    @interp.impl(uop.SX)
    def sx(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.SX):
        qarg: QRBQubit = frame.get(stmt.qarg)
        if qarg.is_active():
            qarg.sim_reg.u(math.pi / 2, math.pi / 2, -math.pi / 2, qarg.addr)
        return ()

    @interp.impl(uop.SXdag)
    def sx_dag(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.SX):
        qarg: QRBQubit = frame.get(stmt.qarg)
        if qarg.is_active():
            qarg.sim_reg.u(math.pi * 1.5, math.pi / 2, math.pi / 2, qarg.addr)
        return ()

    @interp.impl(uop.CSX)
    def csx(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.CSX):
        qarg: QRBQubit = frame.get(stmt.qarg)
        ctrl: QRBQubit = frame.get(stmt.ctrl)
        if qarg.is_active() and ctrl.is_active():
            qarg.sim_reg.mcu([ctrl.addr], qarg.addr, math.pi / 2, math.pi / 2, -math.pi / 2)
        return ()

    @interp.impl(uop.Swap)
    def swap(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.Swap):
        qarg1: QRBQubit = frame.get(stmt.ctrl)
        qarg2: QRBQubit = frame.get(stmt.qarg)
        if qarg1.is_active() and qarg2.is_active():
            qarg1.sim_reg.swap(qarg1.addr, qarg2.addr)
        return ()

    @interp.impl(uop.CSwap)
    def cswap(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.CSwap):
        qarg1: QRBQubit = frame.get(stmt.qarg1)
        qarg2: QRBQubit = frame.get(stmt.qarg2)
        ctrl: QRBQubit = frame.get(stmt.ctrl)
        if qarg1.is_active() and qarg2.is_active():
            qarg1.sim_reg.cswap([ctrl.addr], qarg1.addr, qarg2.addr)
        return ()

    @interp.impl(uop.CX)
    @interp.impl(uop.CZ)
    @interp.impl(uop.CY)
    def control_gate(self, interp: interp.Interpreter, frame: interp.Frame, stmt):
        ctrl: QRBQubit = frame.get(stmt.ctrl)
        qarg: QRBQubit = frame.get(stmt.qarg)
        if ctrl.is_active() and qarg.is_active():
            getattr(qarg.sim_reg, self.GATE_TO_METHOD[stmt.name])([ctrl.addr], qarg.addr)
        return ()

    @interp.impl(uop.CH)
    def ch(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.CH):
        ctrl: QRBQubit = frame.get(stmt.ctrl)
        qarg: QRBQubit = frame.get(stmt.qarg)
        if ctrl.is_active() and qarg.is_active():
            # TODO: replace with qarg.sim_reg.mch([ctrl.addr], qarg.addr)
            #       once qrackbind>=0.3.0 is released (mch not yet exposed).
            #       Decomposition: H = U(pi/2, 0, pi)
            qarg.sim_reg.mcu([ctrl.addr], qarg.addr, math.pi / 2, 0, math.pi)
        return ()

    @interp.impl(uop.CCX)
    def ccx(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.CCX):
        ctrl1: QRBQubit = frame.get(stmt.ctrl1)
        ctrl2: QRBQubit = frame.get(stmt.ctrl2)
        qarg: QRBQubit = frame.get(stmt.qarg)
        if ctrl1.is_active() and ctrl2.is_active() and qarg.is_active():
            qarg.sim_reg.mcx([ctrl1.addr, ctrl2.addr], qarg.addr)
        return ()

    @interp.impl(uop.RX)
    def rx(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.RX):
        qarg: QRBQubit = frame.get(stmt.qarg)
        if qarg.is_active():
            qarg.sim_reg.rx(frame.get(stmt.theta), qarg.addr)
        return ()

    @interp.impl(uop.RY)
    def ry(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.RY):
        qarg: QRBQubit = frame.get(stmt.qarg)
        if qarg.is_active():
            qarg.sim_reg.ry(frame.get(stmt.theta), qarg.addr)
        return ()

    @interp.impl(uop.RZ)
    def rz_gate(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.RZ):
        qarg: QRBQubit = frame.get(stmt.qarg)
        if qarg.is_active():
            qarg.sim_reg.rz(frame.get(stmt.theta), qarg.addr)
        return ()

    @interp.impl(uop.U1)
    def u1(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.U1):
        qarg: QRBQubit = frame.get(stmt.qarg)
        if qarg.is_active():
            qarg.sim_reg.u(0, 0, frame.get(stmt.lam), qarg.addr)
        return ()

    @interp.impl(uop.U2)
    def u2(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.U2):
        qarg: QRBQubit = frame.get(stmt.qarg)
        if qarg.is_active():
            qarg.sim_reg.u(math.pi / 2, frame.get(stmt.phi), frame.get(stmt.lam), qarg.addr)
        return ()

    @interp.impl(uop.CRX)
    def crx(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.CRX):
        ctrl: QRBQubit = frame.get(stmt.ctrl)
        qarg: QRBQubit = frame.get(stmt.qarg)
        if qarg.is_active() and ctrl.is_active():
            # qrackbind has no mcr; CRX(lam) = mcu(controls, target, lam, -pi/2, pi/2)
            qarg.sim_reg.mcu([ctrl.addr], qarg.addr, frame.get(stmt.lam), -math.pi / 2, math.pi / 2)
        return ()

    @interp.impl(uop.CRY)
    def cry(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.CRY):
        ctrl: QRBQubit = frame.get(stmt.ctrl)
        qarg: QRBQubit = frame.get(stmt.qarg)
        if qarg.is_active() and ctrl.is_active():
            # CRY(lam) = mcu(controls, target, lam, 0, 0)
            qarg.sim_reg.mcu([ctrl.addr], qarg.addr, frame.get(stmt.lam), 0, 0)
        return ()

    @interp.impl(uop.CRZ)
    def crz(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.CRZ):
        ctrl: QRBQubit = frame.get(stmt.ctrl)
        qarg: QRBQubit = frame.get(stmt.qarg)
        if qarg.is_active() and ctrl.is_active():
            # qrackbind: mcrz(angle, controls, target)
            qarg.sim_reg.mcrz(frame.get(stmt.lam), [ctrl.addr], qarg.addr)
        return ()

    @interp.impl(uop.CU1)
    def cu1(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.CU1):
        ctrl: QRBQubit = frame.get(stmt.ctrl)
        qarg: QRBQubit = frame.get(stmt.qarg)
        if qarg.is_active() and ctrl.is_active():
            qarg.sim_reg.mcu([ctrl.addr], qarg.addr, 0, 0, frame.get(stmt.lam))
        return ()

    @interp.impl(uop.CU3)
    def cu3(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.CU3):
        ctrl: QRBQubit = frame.get(stmt.ctrl)
        qarg: QRBQubit = frame.get(stmt.qarg)
        if qarg.is_active() and ctrl.is_active():
            qarg.sim_reg.mcu([ctrl.addr], qarg.addr, frame.get(stmt.theta), frame.get(stmt.phi), frame.get(stmt.lam))
        return ()

    @interp.impl(uop.CU)
    def cu(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.CU):
        ctrl: QRBQubit = frame.get(stmt.ctrl)
        qarg: QRBQubit = frame.get(stmt.qarg)
        if qarg.is_active() and ctrl.is_active():
            ctrl.sim_reg.u(0, 0, frame.get(stmt.gamma), ctrl.addr)
            qarg.sim_reg.mcu([ctrl.addr], qarg.addr, frame.get(stmt.theta), frame.get(stmt.phi), frame.get(stmt.lam))
        return ()

    @interp.impl(uop.RXX)
    def rxx(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.RXX):
        a: QRBQubit = frame.get(stmt.qarg)
        b: QRBQubit = frame.get(stmt.ctrl)
        theta = frame.get(stmt.theta)
        sim_reg = a.sim_reg
        if a.is_active() and b.is_active():
            sim_reg.u(math.pi / 2, theta, 0, a.addr)
            sim_reg.h(b.addr)
            sim_reg.mcx([a.addr], b.addr)
            sim_reg.u(0, 0, -theta, b.addr)
            sim_reg.mcx([a.addr], b.addr)
            sim_reg.h(b.addr)
            sim_reg.u(math.pi / 2, -math.pi, math.pi - theta, a.addr)
        return ()

    @interp.impl(uop.RZZ)
    def rzz(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.RZZ):
        a: QRBQubit = frame.get(stmt.qarg)
        b: QRBQubit = frame.get(stmt.ctrl)
        theta = frame.get(stmt.theta)
        sim_reg = a.sim_reg
        if a.is_active() and b.is_active():
            sim_reg.mcx([a.addr], b.addr)
            sim_reg.u(0, 0, theta, b.addr)
            sim_reg.mcx([a.addr], b.addr)
        return ()
