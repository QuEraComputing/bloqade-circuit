from typing import Any

from kirin import interp
from kirin.dialects import ilist
from kirin.interp.exceptions import InterpreterError

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
        qubits: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qubits)
        operator: OperatorRuntimeABC = frame.get(stmt.operator)
        operator.apply(*qubits)

    @interp.impl(qubit.Broadcast)
    def broadcast(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: qubit.Broadcast
    ):
        operator: OperatorRuntimeABC = frame.get(stmt.operator)
        qubits: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qubits)
        operator.broadcast_apply(qubits)

    def _measure_qubit(self, qbit: PyQrackQubit):
        if qbit.is_active():
            return bool(qbit.sim_reg.m(qbit.addr))

    @interp.impl(qubit.MeasureQubitList)
    def measure_qubit_list(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: qubit.MeasureQubitList,
    ):
        qubits: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qubits)
        result = ilist.IList([self._measure_qubit(qbit) for qbit in qubits])
        return (result,)

    @interp.impl(qubit.MeasureQubit)
    def measure_qubit(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: qubit.MeasureQubit
    ):
        qbit: PyQrackQubit = frame.get(stmt.qubit)
        result = self._measure_qubit(qbit)
        return (result,)

    @interp.impl(qubit.MeasureAny)
    def measure_any(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: qubit.MeasureAny
    ):
        input = frame.get(stmt.input)

        if isinstance(input, PyQrackQubit) and input.is_active():
            result = self._measure_qubit
        elif isinstance(input, ilist.IList):
            result = []
            for qbit in input:
                if not isinstance(qbit, PyQrackQubit):
                    raise InterpreterError(f"Cannot measure {type(qbit).__name__}")

                result.append(self._measure_qubit(qbit))
        else:
            raise InterpreterError(f"Cannot measure {type(input).__name__}")

        return (result,)

    @interp.impl(qubit.MeasureAndReset)
    def measure_and_reset(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: qubit.MeasureAndReset,
    ):
        qubits: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qubits)
        result = []
        for qbit in qubits:
            if qbit.is_active():
                result.append(qbit.sim_reg.m(qbit.addr))
            else:
                result.append(None)
            qbit.sim_reg.force_m(qbit.addr, 0)

        return (result,)

    @interp.impl(qubit.Reset)
    def reset(self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: qubit.Reset):
        qubits: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qubits)
        for qbit in qubits:
            qbit.sim_reg.force_m(qbit.addr, 0)
