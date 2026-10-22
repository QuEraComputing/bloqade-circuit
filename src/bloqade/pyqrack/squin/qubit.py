from typing import Any

from kirin import interp
from kirin.dialects import ilist

from bloqade.qubit import stmts as qubit
from bloqade.pyqrack.reg import QubitState, PyQrackQubit, MeasurementResultValue
from bloqade.pyqrack.base import PyQrackInterpreter


@qubit.dialect.register(key="pyqrack")
class PyQrackMethods(interp.MethodTable):
    """Execute qubit operations and compilation directives with PyQrack."""

    @interp.impl(qubit.Barrier)
    def barrier(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: qubit.Barrier
    ):
        """A compilation barrier has no effect during simulation."""
        return ()

    @interp.impl(qubit.New)
    def new_qubit(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: qubit.New
    ):
        """Allocate and bind an active qubit in the simulator's memory."""
        (addr,) = interp.memory.allocate(1)
        qb = PyQrackQubit(addr, interp.memory.sim_reg, QubitState.Active)
        return (qb,)

    def _measure_qubit(self, qbit: PyQrackQubit, interp: PyQrackInterpreter):
        if qbit.is_active():
            m = MeasurementResultValue(bool(qbit.sim_reg.m(qbit.addr)))
        else:
            m = MeasurementResultValue(interp.loss_m_result)

        interp.set_global_measurement_id(m)
        return m

    @interp.impl(qubit.Measure)
    def measure_qubit_list(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: qubit.Measure,
    ):
        """Measure a qubit register and record the measurement identifiers."""
        qubits: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qubits)
        result = ilist.IList([self._measure_qubit(qbit, interp) for qbit in qubits])
        return (result,)

    @interp.impl(qubit.Reset)
    def reset(self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: qubit.Reset):
        """Reset active qubits to zero while leaving lost qubits untouched."""
        qubits: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qubits)
        for qbit in qubits:
            if not qbit.is_active():
                continue

            m = qbit.sim_reg.m(qbit.addr)
            if m == MeasurementResultValue.One:
                qbit.sim_reg.x(qbit.addr)
