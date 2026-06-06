import cirq
from kirin import interp
from kirin.interp import MethodTable, impl
from kirin.dialects import scf

from .base import EmitCirq, EmitCirqFrame
from .classical_control import (
    ConditionError,
    trace_condition,
    build_cirq_condition,
)


@scf.dialect.register(key="emit.cirq")
class EmitCirqScfMethods(MethodTable):
    @impl(scf.IfElse)
    def if_else(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: scf.IfElse):
        try:
            measure_result, polarity = trace_condition(stmt.cond)
        except ConditionError as e:
            # validation should have caught this; re-raise as an interpreter
            # error in case emit_circuit was bypassed.
            raise interp.exceptions.InterpreterError(
                f"Cannot emit if-statement as a Cirq classical control: {e}"
            )

        key_info = frame.measurement_keys.get(measure_result)
        if key_info is None:
            raise interp.exceptions.InterpreterError(
                "Cannot emit if-statement as a Cirq classical control: the "
                "condition's measurement was not emitted before the if-statement."
            )
        key, _ = key_info
        condition = build_cirq_condition(key, polarity)

        # Emit the then-body into a scratch circuit using the *same* frame so
        # that qubit allocation state (qubit_index, entries) is shared with the
        # parent scope, then graft the resulting operations back as classically
        # controlled operations.
        then_block = stmt.then_body.blocks[0]
        saved_circuit = emit.circuit
        emit.circuit = cirq.Circuit()
        try:
            for body_stmt in then_block.stmts:
                if isinstance(body_stmt, scf.Yield):
                    continue
                frame.current_stmt = body_stmt
                results = emit.frame_eval(frame, body_stmt)
                if isinstance(results, tuple) and len(results) != 0:
                    frame.set_values(body_stmt.results, results)
            body_circuit = emit.circuit
        finally:
            emit.circuit = saved_circuit

        for op in body_circuit.all_operations():
            saved_circuit.append(
                op.with_classical_controls(condition),
                strategy=cirq.InsertStrategy.NEW,
            )

        # scf.IfElse here yields nothing (empty Yield) -> no result values.
        return ()
