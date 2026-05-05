from typing import Any

from kirin import interp
from kirin.dialects import ilist

from bloqade.qubit import stmts as qubit
from bloqade.qrb.reg import QubitState, QRBQubit, MeasurementResultValue
from bloqade.qrb.base import QRBInterpreter


@qubit.dialect.register(key="qrb")
class QRBMethods(interp.MethodTable):
    @interp.impl(qubit.New)
    def new_qubit(
        self, interp: QRBInterpreter, frame: interp.Frame, stmt: qubit.New
    ):
        (addr,) = interp.memory.allocate(1)
        qb = QRBQubit(addr, interp.memory.sim_reg, QubitState.Active)
        return (qb,)

    def _measure_qubit(self, qbit: QRBQubit, interp: QRBInterpreter):
        if qbit.is_active():
            # qrackbind: measure(qubit) instead of m(qubit)
            m = MeasurementResultValue(bool(qbit.sim_reg.measure(qbit.addr)))
        else:
            m = MeasurementResultValue(interp.loss_m_result)

        interp.set_global_measurement_id(m)
        return m

    @interp.impl(qubit.Measure)
    def measure_qubit_list(
        self,
        interp: QRBInterpreter,
        frame: interp.Frame,
        stmt: qubit.Measure,
    ):
        qubits: ilist.IList[QRBQubit, Any] = frame.get(stmt.qubits)
        result = ilist.IList([self._measure_qubit(qbit, interp) for qbit in qubits])
        return (result,)

    @interp.impl(qubit.Reset)
    def reset(self, interp: QRBInterpreter, frame: interp.Frame, stmt: qubit.Reset):
        qubits: ilist.IList[QRBQubit, Any] = frame.get(stmt.qubits)
        for qbit in qubits:
            if not qbit.is_active():
                continue
            # qrackbind: measure(qubit)
            m = qbit.sim_reg.measure(qbit.addr)
            if m == MeasurementResultValue.One:
                qbit.sim_reg.x(qbit.addr)
