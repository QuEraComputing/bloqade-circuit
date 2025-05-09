from typing import Any

from kirin import interp
from kirin.interp import InterpreterError
from kirin.dialects import ilist

from bloqade.pyqrack.reg import (
    CBitRef,
    CRegister,
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
        qreg = ilist.IList(
            [
                PyQrackQubit(i, interp.memory.sim_reg, QubitState.Active)
                for i in interp.memory.allocate(n_qubits=n_qubits)
            ]
        )
        return (qreg,)

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
        reg = frame.get(stmt.reg)
        i = frame.get(stmt.idx)
        return (reg[i],)

    @interp.impl(core.CRegGet)
    def creg_get(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: core.CRegGet
    ):
        return (CBitRef(ref=frame.get(stmt.reg), pos=frame.get(stmt.idx)),)

    @interp.impl(core.Measure)
    def measure(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: core.Measure
    ):
        qarg: PyQrackQubit | ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qarg)
        carg: CBitRef | CRegister = frame.get(stmt.carg)

        if isinstance(qarg, PyQrackQubit) and isinstance(carg, CBitRef):
            if qarg.is_active():
                carg.set_value(Measurement(qarg.sim_reg.m(qarg.addr)))
            else:
                carg.set_value(interp.loss_m_result)
        elif isinstance(qarg, ilist.IList) and isinstance(carg, CRegister):
            for i, qubit in enumerate(qarg):
                cbit = CBitRef(carg, i)
                if qubit.is_active():
                    cbit.set_value(Measurement(qubit.sim_reg.m(qubit.addr)))
                else:
                    cbit.set_value(interp.loss_m_result)
        else:
            raise InterpreterError(
                f"Expected measure call on either a single qubit and classical bit, or two registers, but got the types {type(qarg)} and {type(carg)}"
            )

        return ()

    @interp.impl(core.Reset)
    def reset(self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: core.Reset):
        qarg: PyQrackQubit = frame.get(stmt.qarg)

        if bool(qarg.sim_reg.m(qarg.addr)):
            qarg.sim_reg.x(qarg.addr)

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
