from kirin import interp

from bloqade.pyqrack.reg import (
    CBitRef,
    CRegister,
    PyQrackReg,
    QubitState,
    Measurement,
    PyQrackQubit,
)
from bloqade.pyqrack.base import PyQrackInterpreter
from bloqade.qasm2.dialects import core


@core.dialect.register(key="pyqrack")
class PyQrackMethods(interp.MethodTable):

    @interp.impl(core.QRegNew)
    def qreg_new(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: core.QRegNew
    ):
        n_qubits: int = frame.get(stmt.n_qubits)
        return (
            PyQrackReg(
                size=n_qubits,
                sim_reg=interp.memory.sim_reg,
                addrs=interp.memory.allocate(n_qubits),
                qubit_state=[QubitState.Active] * n_qubits,
            ),
        )

    @interp.impl(core.CRegNew)
    def creg_new(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: core.CRegNew
    ):
        n_bits: int = frame.get(stmt.n_bits)
        return (CRegister(size=n_bits),)

    @interp.impl(core.QRegGet)
    def qreg_get(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: core.QRegGet
    ):
        return (PyQrackQubit(ref=frame.get(stmt.reg), pos=frame.get(stmt.idx)),)

    @interp.impl(core.CRegGet)
    def creg_get(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: core.CRegGet
    ):
        return (CBitRef(ref=frame.get(stmt.reg), pos=frame.get(stmt.idx)),)

    @interp.impl(core.Measure)
    def measure(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: core.Measure
    ):
        qarg: PyQrackQubit = frame.get(stmt.qarg)
        carg: CBitRef = frame.get(stmt.carg)
        if qarg.is_active():
            carg.set_value(Measurement(qarg.sim_reg.m(qarg.addr)))
        else:
            carg.set_value(interp.loss_m_result)

        return ()

    @interp.impl(core.Reset)
    def reset(self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: core.Reset):
        qarg: PyQrackQubit = frame.get(stmt.qarg)
        qarg.sim_reg.force_m(qarg.addr, 0)
        return ()

    @interp.impl(core.CRegEq)
    def creg_eq(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: core.CRegEq
    ):
        lhs: CRegister = frame.get(stmt.lhs)
        rhs: CRegister = frame.get(stmt.rhs)
        if len(lhs) != len(rhs):
            return (False,)

        return (all(left is right for left, right in zip(lhs, rhs)),)
