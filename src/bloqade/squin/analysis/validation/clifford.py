from __future__ import annotations

from typing import Any

import numpy as np
from kirin import ir
from kirin.dialects import py
from kirin.validation import ValidationPass

from bloqade.squin import gate
from bloqade.squin.rewrite import SquinU3ToClifford

_CLIFFORD_GATES = (
    gate.stmts.X,
    gate.stmts.Y,
    gate.stmts.Z,
    gate.stmts.H,
    gate.stmts.S,
    gate.stmts.SqrtX,
    gate.stmts.SqrtY,
    gate.stmts.CX,
    gate.stmts.CY,
    gate.stmts.CZ,
)


def _constant_turn(value: ir.SSAValue) -> float | None:
    if not isinstance(value, ir.ResultValue) or not isinstance(
        value.owner, py.Constant
    ):
        return None

    unwrapped = value.owner.value.unwrap()
    if isinstance(unwrapped, (int, float)):
        return float(unwrapped)
    return None


def _is_quarter_turn(value: ir.SSAValue) -> bool:
    turn = _constant_turn(value)
    if turn is None:
        return False

    quarter_turns = turn * 4.0
    return bool(np.isclose(quarter_turns, round(quarter_turns)))


def _is_zero_turn(value: ir.SSAValue) -> bool:
    turn = _constant_turn(value)
    return turn is not None and bool(np.isclose(turn, 0.0))


def _is_clifford_phased_xz(stmt: gate.stmts.PhasedXZ) -> bool:
    if _is_zero_turn(stmt.x_exponent):
        return _is_quarter_turn(stmt.z_exponent)

    return all(
        _is_quarter_turn(angle)
        for angle in (stmt.x_exponent, stmt.z_exponent, stmt.axis_phase_exponent)
    )


def _is_clifford_gate(stmt: gate.stmts.Gate) -> bool:
    if isinstance(stmt, _CLIFFORD_GATES):
        return True
    if isinstance(stmt, gate.stmts.RotationGate):
        return _is_quarter_turn(stmt.angle)
    if isinstance(stmt, gate.stmts.U3):
        return bool(SquinU3ToClifford().decompose_U3_gates(stmt))
    if isinstance(stmt, gate.stmts.PhasedXZ):
        return _is_clifford_phased_xz(stmt)
    return False


class CliffordValidation(ValidationPass):
    def name(self) -> str:
        return "Clifford Validation"

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        errors: list[ir.ValidationError] = []

        for stmt in method.callable_region.walk():
            if not isinstance(stmt, gate.stmts.Gate) or _is_clifford_gate(stmt):
                continue

            errors.append(
                ir.ValidationError(
                    stmt,
                    f"Non-Clifford gate {type(stmt).__name__} is not allowed "
                    "in a Clifford-only SQUIN kernel.",
                )
            )

        return method, errors
