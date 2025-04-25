from typing import Any

from kirin import interp
from kirin.dialects import ilist

from bloqade.squin import qubit
from bloqade.pyqrack.reg import QubitState, PyQrackQubit
from bloqade.pyqrack.base import PyQrackInterpreter


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
        # TODO
        # operator: ir.SSAValue = info.argument(OpType)
        # qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType])
        pass

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

    # @interp.impl(glob.UGate)
    # def ugate(self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: glob.UGate):
    #     registers: ilist.IList[ilist.IList[PyQrackQubit, Any], Any] = frame.get(
    #         stmt.registers
    #     )
    #     theta, phi, lam = (
    #         frame.get(stmt.theta),
    #         frame.get(stmt.phi),
    #         frame.get(stmt.lam),
    #     )

    #     for qreg in registers:
    #         for qarg in qreg:
    #             if qarg.is_active():
    #                 interp.memory.sim_reg.u(qarg.addr, theta, phi, lam)
    #     return ()
