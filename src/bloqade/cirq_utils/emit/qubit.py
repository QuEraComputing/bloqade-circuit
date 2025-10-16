import cirq
from kirin.interp import MethodTable, impl

from bloqade.squin import qubit

from .base import EmitCirq, EmitCirqFrame


@qubit.dialect.register(key="emit.cirq")
class EmitCirqQubitMethods(MethodTable):
    @impl(qubit.New)
    def new(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.New):

        if frame.qubits is not None:
            cirq_qubit = frame.qubits[frame.qubit_index]
        else:
            cirq_qubit = cirq.LineQubit(frame.qubit_index)

        frame.has_allocations = True
        frame.qubit_index += 1
        return (cirq_qubit,)

    @impl(qubit.MeasureQubit)
    def measure_qubit(
        self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.MeasureQubit
    ):
        qbit = frame.get(stmt.qubit)
        frame.circuit.append(cirq.measure(qbit))
        return (emit.void,)

    @impl(qubit.MeasureQubitList)
    def measure_qubit_list(
        self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.MeasureQubitList
    ):
        qbits = frame.get(stmt.qubits)
        frame.circuit.append(cirq.measure(qbits))
        return (emit.void,)

    @impl(qubit.Reset)
    def reset(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.Reset):
        qubits = frame.get(stmt.qubits)
        frame.circuit.append(
            cirq.ResetChannel().on_each(*qubits),
        )
        return ()
