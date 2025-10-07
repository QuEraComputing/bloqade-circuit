import cirq
from kirin.interp import MethodTable, impl

from bloqade.squin import qubit

from .op import OperatorRuntimeABC
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

    @impl(qubit.Apply)
    def apply(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.Apply):
        op: OperatorRuntimeABC = frame.get(stmt.operator)
        qbits = [frame.get(qbit) for qbit in stmt.qubits]
        operations = op.apply(qbits)
        for operation in operations:
            frame.circuit.append(operation)
        return ()

    @impl(qubit.Broadcast)
    def broadcast(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.Broadcast):
        op = frame.get(stmt.operator)
        qbit_lists = [frame.get(qbit) for qbit in stmt.qubits]

        for qbits in zip(*qbit_lists):
            frame.circuit.append(op.apply(qbits))

        return ()

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
