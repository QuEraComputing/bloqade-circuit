import cirq
from kirin.interp import MethodTable, impl

from bloqade.qubit import stmts as qubit

from .base import EmitCirq, EmitCirqFrame


@qubit.dialect.register(key="emit.cirq")
class EmitCirqQubitMethods(MethodTable):
    """Emit method table for the qubit dialect."""

    @impl(qubit.New)
    def new(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.New):
        """Allocate or bind a Cirq qubit for a ``qubit.New`` statement."""
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
        """Append measurement operations and record measurement keys."""
        qbits = frame.get(stmt.qubits)
        meas_op = cirq.measure(qbits)
        emit.circuit.append(meas_op, strategy=cirq.InsertStrategy.NEW)
        key = meas_op.gate.key
        if not isinstance(key, str):
            key = key.name
        emit.measurement_keys[stmt.result] = key
        return (emit.void,)

    @impl(qubit.Reset)
    def reset(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.Reset):
        """Append reset channels for the given qubits."""
        qubits = frame.get(stmt.qubits)
        emit.circuit.append(
            cirq.ResetChannel().on_each(*qubits),
        )
        return ()

    @impl(qubit.IsOne)
    def is_one(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.IsOne):
        """No-op emitter for ``qubit.IsOne`` predicates."""
        return (emit.void,)

    @impl(qubit.IsZero)
    def is_zero(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.IsZero):
        """No-op emitter for ``qubit.IsZero`` predicates."""
        return (emit.void,)

    @impl(qubit.IsLost)
    def is_lost(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: qubit.IsLost):
        """No-op emitter for ``qubit.IsLost`` predicates."""
        return (emit.void,)
