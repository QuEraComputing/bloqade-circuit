import cirq
from kirin.interp import MethodTable, impl

from bloqade.qubit import stmts as qubit

from .base import EmitCirq, EmitCirqFrame


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
        emit.circuit.append(cirq.measure(qbits))
        return (emit.void,)

    @impl(qubit.Reset)
    def reset(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.Reset):
        qubits = frame.get(stmt.qubits)
        emit.circuit.append(
            cirq.ResetChannel().on_each(*qubits),
        )
        return ()
