import cirq
from kirin.dialects import ilist
from kirin.interp import MethodTable, impl

from bloqade.qubit import stmts as qubit

from .base import EmitCirq, EmitCirqFrame, _MeasurementKeyRef


@qubit.dialect.register(key="emit.cirq")
class EmitCirqQubitMethods(MethodTable):
    @impl(qubit.New)
    def new(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.New):
        if frame.qubits is not None:
            cirq_qubit = frame.qubits[frame.qubit_index]
        else:
            cirq_qubit = cirq.LineQubit(frame.qubit_index)

        frame.qubit_index += 1
        return (cirq_qubit,)

    @impl(qubit.Measure)
    def measure_qubit_list(
        self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.Measure
    ):
        qbits = frame.get(stmt.qubits)
        measurement = cirq.measure(qbits)
        emit.circuit.append(measurement, strategy=cirq.InsertStrategy.NEW)

        (key,) = cirq.measurement_key_objs(measurement)
        if len(qbits) == 1:
            return (ilist.IList(data=[_MeasurementKeyRef(key)]),)

        refs = [
            _MeasurementKeyRef(key, bitmask=1 << (len(qbits) - index - 1))
            for index in range(len(qbits))
        ]
        return (ilist.IList(data=refs),)

    @impl(qubit.Reset)
    def reset(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.Reset):
        qubits = frame.get(stmt.qubits)
        emit.circuit.append(
            cirq.ResetChannel().on_each(*qubits),
        )
        return ()
