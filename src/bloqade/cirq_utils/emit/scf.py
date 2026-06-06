import cirq
from kirin.interp import MethodTable, impl
from kirin.dialects import scf

from bloqade.cirq_utils.classical_control import (
    parse_classical_if_condition,
    classical_control_for_condition,
)

from .base import EmitCirq, EmitCirqFrame


@scf.dialect.register(key="emit.cirq")
class __EmitCirqScfMethods(MethodTable):

    @impl(scf.IfElse)
    def if_else(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: scf.IfElse):
        condition = parse_classical_if_condition(stmt.cond)
        assert condition is not None

        key = emit.measurement_keys[condition.measure.result]
        control = classical_control_for_condition(key, condition)

        # NOTE: collect then-body ops into a temporary circuit so we can
        # wrap each one with the classical control before appending.
        prev_circuit = emit.circuit
        emit.circuit = cirq.Circuit()

        for s in stmt.then_body.blocks[0].stmts:
            if isinstance(s, scf.Yield):
                continue
            stmt_results = emit.frame_eval(frame, s)
            if isinstance(stmt_results, tuple) and len(stmt_results) != 0:
                frame.set_values(s.results, stmt_results)

        body_ops = list(emit.circuit.all_operations())
        emit.circuit = prev_circuit

        for op in body_ops:
            emit.circuit.append(op.with_classical_controls(control))

        return ()
