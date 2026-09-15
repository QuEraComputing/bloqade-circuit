"""This module holds the emission of the `jeff.gate` statements."""

from kirin import interp

from jeff import (
    JeffOp,
    JeffValue,
    QubitType,
    CustomGate,
    KnownGates,
    WellKnowGate,
    pauli_rotation,
)
from bloqade.jeff.dialects import stmts

from .base import EmitJeff, JeffFrame


def _gate_data(stmt: stmts.Gate) -> WellKnowGate | CustomGate:
    """Return the jeff instruction data of a gate statement."""
    num_controls = len(stmt.controls)
    if stmt.gate_name in KnownGates:
        return WellKnowGate(stmt.gate_name, num_controls, stmt.adjoint, stmt.power)
    return CustomGate(
        stmt.gate_name,
        len(stmt.targets),
        len(stmt.params),
        num_controls,
        stmt.adjoint,
        stmt.power,
    )


@stmts.gate.dialect.register(key="emit.jeff")
class _Gate(interp.MethodTable):
    """Emit the `jeff.gate` statements."""

    @interp.impl(stmts.Gate)
    def gate(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.Gate
    ) -> tuple[JeffValue, ...]:
        """Emit a quantum gate."""
        qubits = [frame.get(value) for value in (*stmt.targets, *stmt.controls)]
        params = [frame.get(value) for value in stmt.params]
        outputs = [JeffValue(QubitType()) for _ in qubits]
        frame.push(
            JeffOp(
                "qubit",
                "gate",
                [*qubits, *params],
                outputs,
                instruction_data=_gate_data(stmt),
            )
        )
        return tuple(outputs)

    @interp.impl(stmts.Ppr)
    def ppr(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.Ppr
    ) -> tuple[JeffValue, ...]:
        """Emit a Pauli product rotation."""
        op = frame.push(
            pauli_rotation(
                frame.get(stmt.angle),
                list(stmt.pauli_string),
                [frame.get(value) for value in stmt.targets],
                control_qubits=[frame.get(value) for value in stmt.controls],
                adjoint=stmt.adjoint,
                power=stmt.power,
            )
        )
        return tuple(op.outputs)
