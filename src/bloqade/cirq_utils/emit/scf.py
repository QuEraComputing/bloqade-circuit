import cirq
from kirin import interp
from kirin.dialects import scf

from .base import EmitCirq, EmitCirqFrame
from .classical_control import (
    cirq_condition_for_key,
    get_measurement_condition,
    unsupported_condition_error,
)


@scf.dialect.register(key="emit.cirq")
class EmitCirqScfMethods(interp.MethodTable):
    @interp.impl(scf.IfElse)
    def if_else(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: scf.IfElse):
        measurement_condition = get_measurement_condition(stmt.cond)
        if measurement_condition is None:
            raise unsupported_condition_error()

        key = frame.measurement_keys.get(measurement_condition.measurement)
        if key is None:
            raise interp.exceptions.InterpreterError(
                "Cirq if emission could not find a measurement key for the condition."
            )

        parent_circuit = emit.circuit
        then_circuit = cirq.Circuit()
        old_block = frame.current_block
        old_stmt = frame.current_stmt

        emit.circuit = then_circuit
        try:
            for block in stmt.then_body.blocks:
                frame.current_block = block
                for child in block.stmts:
                    if isinstance(child, scf.Yield):
                        continue
                    frame.current_stmt = child
                    child_results = emit.frame_eval(frame, child)
                    if isinstance(child_results, tuple) and child_results:
                        frame.set_values(child.results, child_results)
        finally:
            emit.circuit = parent_circuit
            frame.current_block = old_block
            frame.current_stmt = old_stmt

        condition = cirq_condition_for_key(key, measurement_condition.value)
        controlled_ops = [
            op.with_classical_controls(condition) for op in then_circuit.all_operations()
        ]
        emit.circuit.append(controlled_ops, strategy=cirq.InsertStrategy.NEW)
        return ()
