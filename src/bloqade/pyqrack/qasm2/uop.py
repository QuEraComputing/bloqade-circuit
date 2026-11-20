import math

from kirin import interp

from pyqrack.pauli import Pauli
from bloqade.pyqrack.reg import PyQrackQubit
from bloqade.qasm2.dialects import uop


@uop.dialect.register(key="pyqrack")
class PyQrackMethods(interp.MethodTable):
    """PyQrack implementations of the qasm2 `uop` statements."""

    GATE_TO_METHOD = {
        "x": "x",
        "y": "y",
        "z": "z",
        "h": "h",
        "s": "s",
        "t": "t",
        "cx": "mcx",
        "CX": "mcx",
        "cz": "mcz",
        "cy": "mcy",
        "ch": "mch",
        "sdag": "adjs",
        "sdg": "adjs",
        "tdag": "adjt",
        "tdg": "adjt",
    }

    AXIS_MAP = {
        "rx": Pauli.PauliX,
        "ry": Pauli.PauliY,
        "rz": Pauli.PauliZ,
        "crx": Pauli.PauliX,
        "cry": Pauli.PauliY,
        "crz": Pauli.PauliZ,
    }

    @interp.impl(uop.Barrier)
    def barrier(
        self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.Barrier
    ):
        """Barriers are a no-op in the simulator."""
        return ()

    @interp.impl(uop.X)
    @interp.impl(uop.Y)
    @interp.impl(uop.Z)
    @interp.impl(uop.H)
    @interp.impl(uop.S)
    @interp.impl(uop.Sdag)
    @interp.impl(uop.T)
    @interp.impl(uop.Tdag)
    def single_qubit_gate(
        self,
        interp: interp.Interpreter,
        frame: interp.Frame,
        stmt: uop.SingleQubitGate,
    ):
        """Apply a fixed single-qubit gate."""
        qarg: PyQrackQubit = frame.get(stmt.qarg)
        if qarg.is_active():
            getattr(qarg.sim_reg, self.GATE_TO_METHOD[stmt.name])(qarg.addr)
        return ()

    @interp.impl(uop.UGate)
    def ugate(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.UGate):
        """Apply a U(theta, phi, lam) gate."""
        qarg: PyQrackQubit = frame.get(stmt.qarg)
        if qarg.is_active():
            qarg.sim_reg.u(
                qarg.addr,
                frame.get(stmt.theta),
                frame.get(stmt.phi),
                frame.get(stmt.lam),
            )
        return ()

    @interp.impl(uop.Id)
    def id(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.Id):
        """The identity gate is a no-op."""
        return ()

    @interp.impl(uop.SX)
    def sx(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.SX):
        """Apply sqrt(X), up to a global phase."""
        qarg: PyQrackQubit = frame.get(stmt.qarg)
        if qarg.is_active():
            qarg.sim_reg.u(qarg.addr, math.pi / 2, -math.pi / 2, math.pi / 2)
        return ()

    @interp.impl(uop.SXdag)
    def sx_dag(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.SX):
        """Apply sqrt(X)^dagger, up to a global phase."""
        qarg: PyQrackQubit = frame.get(stmt.qarg)
        if qarg.is_active():
            qarg.sim_reg.u(qarg.addr, math.pi / 2, math.pi / 2, -math.pi / 2)
        return ()

    @interp.impl(uop.CSX)
    def csx(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.CSX):
        """Apply controlled-sqrt(X)."""
        qarg: PyQrackQubit = frame.get(stmt.qarg)
        ctrl: PyQrackQubit = frame.get(stmt.ctrl)
        if qarg.is_active() and ctrl.is_active():
            # sqrt(X) = H S H exactly, so the controlled gate gets no phase on the control
            qarg.sim_reg.h(qarg.addr)
            qarg.sim_reg.mcs([ctrl.addr], qarg.addr)
            qarg.sim_reg.h(qarg.addr)
        return ()

    @interp.impl(uop.Swap)
    def swap(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.Swap):
        """Swap two qubits."""
        qarg1: PyQrackQubit = frame.get(stmt.ctrl)
        qarg2: PyQrackQubit = frame.get(stmt.qarg)
        if qarg1.is_active() and qarg2.is_active():
            qarg1.sim_reg.swap(qarg1.addr, qarg2.addr)
        return ()

    @interp.impl(uop.CSwap)
    def cswap(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.CSwap):
        """Apply a controlled swap."""
        qarg1: PyQrackQubit = frame.get(stmt.qarg1)
        qarg2: PyQrackQubit = frame.get(stmt.qarg2)
        ctrl: PyQrackQubit = frame.get(stmt.ctrl)
        if qarg1.is_active() and qarg2.is_active():
            qarg1.sim_reg.cswap([ctrl.addr], qarg1.addr, qarg2.addr)
        return ()

    @interp.impl(uop.CX)
    @interp.impl(uop.CZ)
    @interp.impl(uop.CY)
    @interp.impl(uop.CH)
    def control_gate(
        self,
        interp: interp.Interpreter,
        frame: interp.Frame,
        stmt: uop.CX | uop.CZ | uop.CY,
    ):
        """Apply a singly-controlled X, Y, Z or H gate."""
        ctrl: PyQrackQubit = frame.get(stmt.ctrl)
        qarg: PyQrackQubit = frame.get(stmt.qarg)
        if ctrl.is_active() and qarg.is_active():
            getattr(qarg.sim_reg, self.GATE_TO_METHOD[stmt.name])(
                [ctrl.addr], qarg.addr
            )
        return ()

    @interp.impl(uop.CCX)
    def ccx(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.CCX):
        """Apply a Toffoli gate."""
        ctrl1: PyQrackQubit = frame.get(stmt.ctrl1)
        ctrl2: PyQrackQubit = frame.get(stmt.ctrl2)
        qarg: PyQrackQubit = frame.get(stmt.qarg)
        if ctrl1.is_active() and ctrl2.is_active() and qarg.is_active():
            qarg.sim_reg.mcx([ctrl1.addr, ctrl2.addr], qarg.addr)
        return ()

    @interp.impl(uop.RX)
    @interp.impl(uop.RY)
    @interp.impl(uop.RZ)
    def rotation(
        self,
        interp: interp.Interpreter,
        frame: interp.Frame,
        stmt: uop.RX | uop.RY | uop.RZ,
    ):
        """Apply a rotation about the X, Y or Z axis."""
        qarg: PyQrackQubit = frame.get(stmt.qarg)
        if qarg.is_active():
            qarg.sim_reg.r(self.AXIS_MAP[stmt.name], frame.get(stmt.theta), qarg.addr)
        return ()

    @interp.impl(uop.U1)
    def u1(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.U1):
        """Apply a U1(lam) phase gate."""
        qarg: PyQrackQubit = frame.get(stmt.qarg)
        if qarg.is_active():
            qarg.sim_reg.u(qarg.addr, 0, 0, frame.get(stmt.lam))
        return ()

    @interp.impl(uop.U2)
    def u2(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.U2):
        """Apply a U2(phi, lam) gate."""
        qarg: PyQrackQubit = frame.get(stmt.qarg)
        if qarg.is_active():
            qarg.sim_reg.u(
                qarg.addr, math.pi / 2, frame.get(stmt.phi), frame.get(stmt.lam)
            )
        return ()

    @interp.impl(uop.CRX)
    @interp.impl(uop.CRY)
    @interp.impl(uop.CRZ)
    def crx(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.CRX):
        """Apply a controlled rotation about the X, Y or Z axis."""
        ctrl: PyQrackQubit = frame.get(stmt.ctrl)
        qarg: PyQrackQubit = frame.get(stmt.qarg)
        if qarg.is_active() and ctrl.is_active():
            qarg.sim_reg.mcr(
                self.AXIS_MAP[stmt.name], frame.get(stmt.lam), [ctrl.addr], qarg.addr
            )
        return ()

    @interp.impl(uop.CU1)
    def cu1(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.CU1):
        """Apply a controlled U1(lam) gate."""
        ctrl: PyQrackQubit = frame.get(stmt.ctrl)
        qarg: PyQrackQubit = frame.get(stmt.qarg)
        if qarg.is_active() and ctrl.is_active():
            qarg.sim_reg.mcu([ctrl.addr], qarg.addr, 0, 0, frame.get(stmt.lam))
        return ()

    @interp.impl(uop.CU3)
    def cu3(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.CU3):
        """Apply a controlled U3(theta, phi, lam) gate."""
        ctrl: PyQrackQubit = frame.get(stmt.ctrl)
        qarg: PyQrackQubit = frame.get(stmt.qarg)
        if qarg.is_active() and ctrl.is_active():
            qarg.sim_reg.mcu(
                [ctrl.addr],
                qarg.addr,
                frame.get(stmt.theta),
                frame.get(stmt.phi),
                frame.get(stmt.lam),
            )
        return ()

    @interp.impl(uop.CU)
    def cu(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.CU):
        """Apply a controlled U(theta, phi, lam) gate with phase gamma on the control."""
        ctrl: PyQrackQubit = frame.get(stmt.ctrl)
        qarg: PyQrackQubit = frame.get(stmt.qarg)
        if qarg.is_active() and ctrl.is_active():
            ctrl.sim_reg.u(ctrl.addr, 0, 0, frame.get(stmt.gamma))
            qarg.sim_reg.mcu(
                [ctrl.addr],
                qarg.addr,
                frame.get(stmt.theta),
                frame.get(stmt.phi),
                frame.get(stmt.lam),
            )
        return ()

    @interp.impl(uop.RXX)
    def rxx(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.RXX):
        """Apply an RXX(theta) gate."""
        a: PyQrackQubit = frame.get(stmt.qarg)
        b: PyQrackQubit = frame.get(stmt.ctrl)
        theta = frame.get(stmt.theta)
        sim_reg = a.sim_reg
        if a.is_active() and b.is_active():
            sim_reg.u(a.addr, math.pi / 2, theta, 0)
            sim_reg.h(b.addr)
            sim_reg.mcx([a.addr], b.addr)
            sim_reg.u(b.addr, 0, 0, -theta)
            sim_reg.mcx([a.addr], b.addr)
            sim_reg.h(b.addr)
            sim_reg.u(a.addr, math.pi / 2, -math.pi, math.pi - theta)

        return ()

    @interp.impl(uop.RZZ)
    def rzz(self, interp: interp.Interpreter, frame: interp.Frame, stmt: uop.RZZ):
        """Apply an RZZ(theta) gate."""
        a: PyQrackQubit = frame.get(stmt.qarg)
        b: PyQrackQubit = frame.get(stmt.ctrl)
        theta = frame.get(stmt.theta)
        sim_reg = a.sim_reg
        if a.is_active() and b.is_active():
            sim_reg.mcx([a.addr], b.addr)
            sim_reg.u(b.addr, 0, 0, theta)
            sim_reg.mcx([a.addr], b.addr)

        return ()
