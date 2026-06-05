from typing import Any

from kirin import ir, types
from kirin.dialects import py, scf
from kirin.validation import ValidationPass

from bloqade.qubit import stmts as qubit_stmts
from bloqade.squin import gate
from bloqade.types import MeasurementResultType


def _is_empty_else(stmt: scf.IfElse) -> bool:
    if not stmt.else_body.blocks:
        return True

    else_stmts = list(stmt.else_body.blocks[0].stmts)
    return len(else_stmts) == 1 and isinstance(else_stmts[0], scf.Yield)


def _constant_bit(ssa: ir.SSAValue) -> int | None:
    if not isinstance(ssa, ir.ResultValue) or not isinstance(ssa.owner, py.Constant):
        return None

    value = ssa.owner.value.unwrap()
    if value in (0, 1, False, True):
        return int(value)
    return None


def _measurement_operand(ssa: ir.SSAValue) -> ir.SSAValue | None:
    if ssa.type != MeasurementResultType:
        return None
    return ssa


def _is_single_measurement_result(ssa: ir.SSAValue) -> bool:
    if not isinstance(ssa, ir.ResultValue):
        return False

    owner = ssa.owner
    if not isinstance(owner, py.indexing.GetItem):
        return False

    if _constant_bit(owner.index) is None:
        return False

    if not isinstance(owner.obj, ir.ResultValue):
        return False

    measure_stmt = owner.obj.owner
    if not isinstance(measure_stmt, qubit_stmts.Measure):
        return False

    measure_type = measure_stmt.qubits.type
    if not measure_type.vars:
        return False

    length = measure_type.vars[1]
    return isinstance(length, types.Literal) and length.data == 1


def _supported_condition(stmt: scf.IfElse) -> bool:
    if not isinstance(stmt.cond, ir.ResultValue) or not isinstance(
        stmt.cond.owner, py.cmp.Eq
    ):
        return False

    lhs = stmt.cond.owner.lhs
    rhs = stmt.cond.owner.rhs
    lhs_measurement = _measurement_operand(lhs)
    rhs_measurement = _measurement_operand(rhs)

    if lhs_measurement is not None and _constant_bit(rhs) is not None:
        return _is_single_measurement_result(lhs_measurement)

    if rhs_measurement is not None and _constant_bit(lhs) is not None:
        return _is_single_measurement_result(rhs_measurement)

    return False


def _count_then_gates(stmt: scf.IfElse) -> int:
    return sum(
        1 for child in stmt.then_body.walk() if isinstance(child, gate.stmts.Gate)
    )


class CirqClassicalControlValidation(ValidationPass):
    def name(self) -> str:
        return "Cirq Classical Control Validation"

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        errors: list[ir.ValidationError] = []

        for stmt in method.code.walk():
            if not isinstance(stmt, scf.IfElse):
                continue

            if not _supported_condition(stmt):
                errors.append(
                    ir.ValidationError(
                        stmt,
                        "Cirq emission supports if statements only when the condition "
                        "compares a single measurement result to 0, 1, False, or True.",
                    )
                )

            if not _is_empty_else(stmt):
                errors.append(
                    ir.ValidationError(
                        stmt,
                        "Cirq emission supports measurement-controlled if statements "
                        "only when the else body is empty.",
                    )
                )

            if _count_then_gates(stmt) != 1:
                errors.append(
                    ir.ValidationError(
                        stmt,
                        "Cirq emission supports measurement-controlled if statements "
                        "only when the then body contains exactly one gate operation.",
                    )
                )

        return None, errors
