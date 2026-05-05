from typing import Any

from kirin import interp
from kirin.interp import InterpreterError
from kirin.dialects import ilist

from bloqade.qrb.reg import (
    CBitRef,
    CRegister,
    QubitState,
    QRBQubit,
    MeasurementResultValue,
)
from bloqade.qrb.base import QRBInterpreter
from bloqade.qasm2.dialects import core


@core.dialect.register(key="qrb")
class QRBMethods(interp.MethodTable):
    @interp.impl(core.QRegNew)
    def qreg_new(
        self, interp: QRBInterpreter, frame: interp.Frame, stmt: core.QRegNew
    ):
        n_qubits: int = frame.get(stmt.n_qubits)
        qreg = ilist.IList(
            [
                QRBQubit(i, interp.memory.sim_reg, QubitState.Active)
                for i in interp.memory.allocate(n_qubits=n_qubits)
            ]
        )
        return (qreg,)

    @interp.impl(core.CRegNew)
    def creg_new(
        self, interp: QRBInterpreter, frame: interp.Frame, stmt: core.CRegNew
    ):
        n_bits: int = frame.get(stmt.n_bits)
        return (CRegister(size=n_bits),)

    @interp.impl(core.QRegGet)
    def qreg_get(
        self, interp: QRBInterpreter, frame: interp.Frame, stmt: core.QRegGet
    ):
        reg = frame.get(stmt.reg)
        i = frame.get(stmt.idx)
        return (reg[i],)

    @interp.impl(core.CRegGet)
    def creg_get(
        self, interp: QRBInterpreter, frame: interp.Frame, stmt: core.CRegGet
    ):
        return (CBitRef(ref=frame.get(stmt.reg), pos=frame.get(stmt.idx)),)

    @interp.impl(core.Measure)
    def measure(
        self, interp: QRBInterpreter, frame: interp.Frame, stmt: core.Measure
    ):
        qarg: QRBQubit | ilist.IList[QRBQubit, Any] = frame.get(stmt.qarg)
        carg: CBitRef | CRegister = frame.get(stmt.carg)

        if isinstance(qarg, QRBQubit) and isinstance(carg, CBitRef):
            if qarg.is_active():
                # qrackbind: measure(qubit) instead of m(qubit)
                carg.set_value(MeasurementResultValue(qarg.sim_reg.measure(qarg.addr)))
            else:
                carg.set_value(interp.loss_m_result)
        elif isinstance(qarg, ilist.IList) and isinstance(carg, CRegister):
            for i, qubit in enumerate(qarg):
                cbit = CBitRef(carg, i)
                if qubit.is_active():
                    cbit.set_value(
                        MeasurementResultValue(qubit.sim_reg.measure(qubit.addr))
                    )
                else:
                    cbit.set_value(interp.loss_m_result)
        else:
            raise InterpreterError(
                f"Expected measure call on either a single qubit and classical bit, "
                f"or two registers, but got the types {type(qarg)} and {type(carg)}"
            )

        return ()

    @interp.impl(core.Reset)
    def reset(self, interp: QRBInterpreter, frame: interp.Frame, stmt: core.Reset):
        qarg: QRBQubit = frame.get(stmt.qarg)

        # qrackbind: measure(qubit) instead of m(qubit)
        if bool(qarg.sim_reg.measure(qarg.addr)):
            qarg.sim_reg.x(qarg.addr)

        return ()

    @interp.impl(core.CRegEq)
    def creg_eq(
        self, interp: QRBInterpreter, frame: interp.Frame, stmt: core.CRegEq
    ):
        lhs: CRegister = frame.get(stmt.lhs)
        rhs: CRegister = frame.get(stmt.rhs)
        if len(lhs) != len(rhs):
            return (False,)

        return (all(left is right for left, right in zip(lhs, rhs)),)
