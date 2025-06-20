import cirq
from kirin.interp import MethodTable, impl

from ... import qubit
from .op import OperatorRuntimeABC
from .emit_circuit import EmitCirq, EmitCirqFrame


@qubit.dialect.register(key="emit.cirq")
class EmitCirqQubitMethods(MethodTable):
    @impl(qubit.New)
    def new(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.New):
        n_qubits = frame.get(stmt.n_qubits)

        if frame.qubits is not None:
            cirq_qubits = [frame.qubits[i + frame.qubit_index] for i in range(n_qubits)]
        else:
            cirq_qubits = [
                cirq.LineQubit(i + frame.qubit_index) for i in range(n_qubits)
            ]

        frame.qubit_index += n_qubits
        return (cirq_qubits,)

    @impl(qubit.Apply)
    def apply(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.Apply):
        op: OperatorRuntimeABC = frame.get(stmt.operator)
        qbits = frame.get(stmt.qubits)
        operations = op.apply(qbits)
        for operation in operations:
            frame.circuit.append(operation)
        return ()

    @impl(qubit.Broadcast)
    def broadcast(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.Broadcast):
        op = frame.get(stmt.operator)
        qbits = frame.get(stmt.qubits)

        cirq_ops = []
        for qbit in qbits:
            cirq_ops.extend(op.apply([qbit]))

        frame.circuit.append(cirq.Moment(cirq_ops))
        return ()

    @impl(qubit.MeasureQubit)
    def measure_qubit(
        self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.MeasureQubit
    ):
        qbit = frame.get(stmt.qubit)
        frame.circuit.append(cirq.measure(qbit))
        return ()

    @impl(qubit.MeasureQubitList)
    def measure_qubit_list(
        self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.MeasureQubitList
    ):
        qbits = frame.get(stmt.qubits)
        frame.circuit.append(cirq.measure(qbits))
        return ()
