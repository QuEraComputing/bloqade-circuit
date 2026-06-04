from typing import Any

from kirin import ir
from kirin.dialects import ilist, py, scf
from kirin.validation import ValidationPass

from bloqade.qubit import stmts as qubit
from bloqade.squin import gate


def _constant_value(value: ir.SSAValue) -> Any:
    owner = value.owner
    if isinstance(owner, py.Constant):
        return owner.value.data
    return None


def _is_single_measurement_result(value: ir.SSAValue) -> bool:
    owner = value.owner
    if not isinstance(owner, py.indexing.GetItem):
        return False

    if not isinstance(owner.index.owner, py.Constant):
        return False

    measure_stmt = owner.obj.owner
    if not isinstance(measure_stmt, qubit.Measure):
        return False

    qubits_stmt = measure_stmt.qubits.owner
    return isinstance(qubits_stmt, ilist.New) and len(qubits_stmt.values) == 1


def _is_measurement_comparison(stmt: ir.Statement) -> bool:
    if not isinstance(stmt, (py.cmp.Eq, py.cmp.NotEq)):
        return False

    lhs_is_measurement = _is_single_measurement_result(stmt.lhs)
    rhs_is_measurement = _is_single_measurement_result(stmt.rhs)

    if lhs_is_measurement == rhs_is_measurement:
        return False

    expected = _constant_value(stmt.rhs if lhs_is_measurement else stmt.lhs)
    return expected in (False, True, 0, 1)


def _is_empty_else(stmt: scf.IfElse) -> bool:
    if len(stmt.else_body.blocks) != 1:
        return False

    else_stmts = list(stmt.else_body.blocks[0].stmts)
    return len(else_stmts) == 1 and isinstance(else_stmts[0], scf.Yield)


def _then_gate_count(stmt: scf.IfElse) -> int:
    if len(stmt.then_body.blocks) != 1:
        return 0

    return sum(
        1
        for child in stmt.then_body.blocks[0].stmts
        if isinstance(child, gate.stmts.Gate)
    )


class CirqClassicalControlValidation(ValidationPass):
    def name(self) -> str:
        return "Cirq classical control validation"

    def run(self, method: ir.Method) -> tuple[None, list[ir.ValidationError]]:
        errors: list[ir.ValidationError] = []

        for stmt in method.callable_region.walk():
            if not isinstance(stmt, scf.IfElse):
                continue

            if not _is_measurement_comparison(stmt.cond.owner):
                errors.append(
                    ir.ValidationError(
                        stmt,
                        "Cirq emission only supports if-statements controlled by a "
                        "single measurement compared with True/False or 1/0.",
                    )
                )

            if not _is_empty_else(stmt):
                errors.append(
                    ir.ValidationError(
                        stmt,
                        "Cirq emission only supports measurement-controlled if-statements "
                        "with an empty else body.",
                    )
                )

            if _then_gate_count(stmt) != 1:
                errors.append(
                    ir.ValidationError(
                        stmt,
                        "Cirq emission only supports measurement-controlled if-statements "
                        "whose then body contains exactly one gate operation.",
                    )
                )

        return None, errors
