import cirq
from kirin.interp import MethodTable, impl

from bloqade.squin import qubit

from .base import EmitCirq, EmitCirqFrame


@qubit.dialect.register(key="emit.cirq")
class EmitCirqQubitMethods(MethodTable):
    @impl(qubit.New)
    def new(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.New):
        n_qubits = frame.get(stmt.n_qubits)

        if frame.qubits is not None:
            cirq_qubits = tuple(
                frame.qubits[i + frame.qubit_index] for i in range(n_qubits)
            )
        else:
            cirq_qubits = tuple(
                cirq.LineQubit(i + frame.qubit_index) for i in range(n_qubits)
            )

        frame.qubit_index += n_qubits
        return (cirq_qubits,)

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
