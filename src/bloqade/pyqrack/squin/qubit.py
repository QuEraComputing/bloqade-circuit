from typing import Any

from kirin import interp
from kirin.dialects import ilist

from bloqade.squin import qubit
from bloqade.pyqrack.reg import QubitState, PyQrackQubit
from bloqade.pyqrack.base import PyQrackInterpreter

from .runtime import OperatorRuntimeABC


@qubit.dialect.register(key="pyqrack")
class PyQrackMethods(interp.MethodTable):
    @interp.impl(qubit.New)
    def new(self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: qubit.New):
        n_qubits: int = frame.get(stmt.n_qubits)
        qreg = ilist.IList(
            [
                PyQrackQubit(i, interp.memory.sim_reg, QubitState.Active)
                for i in interp.memory.allocate(n_qubits=n_qubits)
            ]
        )
        return (qreg,)

    @interp.impl(qubit.Apply)
    def apply(self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: qubit.Apply):
        operator: OperatorRuntimeABC = frame.get(stmt.operator)
        qubits: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qubits)
        operator.apply(*qubits)

    @interp.impl(qubit.Broadcast)
    def broadcast(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: qubit.Broadcast
    ):
        operator: OperatorRuntimeABC = frame.get(stmt.operator)
        qubits: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qubits)
        operator.broadcast_apply(qubits)

    @interp.impl(qubit.Measure)
    def measure(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: qubit.Measure
    ):
        qubits: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qubits)
        result = [qbit.sim_reg.m(qbit.addr) for qbit in qubits]
        return (result,)

    @interp.impl(qubit.MeasureAndReset)
    def measure_and_reset(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: qubit.MeasureAndReset,
    ):
        qubits: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qubits)
        result = [qbit.sim_reg.m(qbit.addr) for qbit in qubits]
        for qbit in qubits:
            qbit.sim_reg.force_m(qbit.addr, 0)

        return (result,)

    @interp.impl(qubit.Reset)
    def reset(self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: qubit.Reset):
        qubits: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qubits)
        for qbit in qubits:
            qbit.sim_reg.force_m(qbit.addr, 0)
