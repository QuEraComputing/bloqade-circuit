"""Validation for emitting ``scf.IfElse`` statements as Cirq classical controls.

An ``if`` statement can be emitted as a classical control only when:

* its condition derives from a single measurement, compared against
  ``0``/``1``/``False``/``True`` or wrapped in ``is_one`` / ``is_zero``;
* the ``else`` body is empty;
* the ``then`` body contains exactly one gate operation and no allocations,
  measurements, resets, nested control flow or sub-kernel calls.
"""

from typing import Any

from kirin import ir
from kirin.dialects import scf, func
from kirin.validation import ValidationPass

from bloqade.qubit import stmts as qubit_stmts
from bloqade.squin import gate

from .classical_control import (
    ConditionError,
    trace_condition,
    measure_num_qubits,
)

# Statements that must never appear inside a classically-controlled then-body.
_FORBIDDEN_IN_BODY = (
    qubit_stmts.New,
    qubit_stmts.Measure,
    qubit_stmts.Reset,
    scf.IfElse,
    scf.For,
    func.Invoke,
    func.Call,
)


def _validate_if_else(stmt: scf.IfElse, errors: list[ir.ValidationError]) -> None:
    # --- else body must be empty (only a terminating yield) ---
    for block in stmt.else_body.blocks:
        for child in block.stmts:
            if not isinstance(child, scf.Yield):
                errors.append(
                    ir.ValidationError(
                        stmt,
                        "Cannot emit an if-statement with a non-empty else body "
                        "as a Cirq classical control.",
                    )
                )
                break

    # --- then body must contain exactly one gate and nothing disallowed ---
    gate_count = 0
    then_blocks = stmt.then_body.blocks
    if len(then_blocks) != 1:
        errors.append(
            ir.ValidationError(
                stmt,
                "Cannot emit an if-statement whose then-body has multiple blocks "
                "as a Cirq classical control.",
            )
        )
    for block in then_blocks:
        for child in block.stmts:
            if isinstance(child, gate.stmts.Gate):
                gate_count += 1
            elif isinstance(child, _FORBIDDEN_IN_BODY):
                errors.append(
                    ir.ValidationError(
                        stmt,
                        "Cannot emit an if-statement as a Cirq classical control: "
                        f"the then-body contains an unsupported statement "
                        f"'{type(child).__name__}'. Only a single gate operation "
                        "is allowed.",
                    )
                )

    if gate_count != 1:
        errors.append(
            ir.ValidationError(
                stmt,
                "Cannot emit an if-statement as a Cirq classical control: the "
                f"then-body must contain exactly one gate operation, found "
                f"{gate_count}.",
            )
        )

    # --- condition must resolve to a single-qubit measurement ---
    try:
        measure_result, _ = trace_condition(stmt.cond)
    except ConditionError as e:
        errors.append(ir.ValidationError(stmt, f"Unsupported if-condition: {e}."))
        return

    num_qubits = measure_num_qubits(measure_result)
    if num_qubits is not None and num_qubits != 1:
        errors.append(
            ir.ValidationError(
                stmt,
                "Cannot emit an if-statement as a Cirq classical control: the "
                "condition must be based on a single-qubit measurement, but the "
                f"measurement acts on {num_qubits} qubits.",
            )
        )


class CirqClassicalControlValidation(ValidationPass):
    """Validate that every ``scf.IfElse`` in a kernel can be emitted as a Cirq
    classical control."""

    def name(self) -> str:
        return "Cirq Classical Control Validation"

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        errors: list[ir.ValidationError] = []
        for node in method.callable_region.walk():
            if isinstance(node, scf.IfElse):
                _validate_if_else(node, errors)
        return None, errors
