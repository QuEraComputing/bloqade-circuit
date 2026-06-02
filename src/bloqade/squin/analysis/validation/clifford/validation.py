import math
from typing import Any

from kirin import ir
from kirin.validation import ValidationPass

from bloqade.squin import gate
from bloqade.squin.rewrite.U3_to_clifford import (
    RX_HALF_PI_TO_CLIFFORD,
    RY_HALF_PI_TO_CLIFFORD,
    RZ_HALF_PI_TO_CLIFFORD,
    SquinU3ToClifford,
)

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


class CliffordValidation(ValidationPass):
    """Validate that a Squin kernel contains only Clifford gates."""

    def name(self) -> str:
        return "Clifford Validation"

    def _add_non_clifford_error(
        self,
        stmt: ir.Statement,
        errors: list[ir.ValidationError],
    ) -> None:
        errors.append(
            ir.ValidationError(
                stmt,
                f"Non-Clifford gate {type(stmt).__name__} is not allowed "
                "in Clifford-only Squin kernels.",
            )
        )

    @staticmethod
    def _is_clifford_rotation(stmt: gate.stmts.RotationGate) -> bool:
        rewrite = SquinU3ToClifford()
        if isinstance(stmt, gate.stmts.Rx):
            clifford_map = RX_HALF_PI_TO_CLIFFORD
        elif isinstance(stmt, gate.stmts.Ry):
            clifford_map = RY_HALF_PI_TO_CLIFFORD
        elif isinstance(stmt, gate.stmts.Rz):
            clifford_map = RZ_HALF_PI_TO_CLIFFORD
        else:
            return False

        angle = rewrite.get_constant(stmt.angle)
        if angle is None:
            return False

        angle_half_pi = rewrite.resolve_angle(angle * math.tau)
        return angle_half_pi is not None and angle_half_pi in clifford_map

    @staticmethod
    def _is_clifford_u3(stmt: gate.stmts.U3) -> bool:
        return len(SquinU3ToClifford().decompose_U3_gates(stmt)) > 0

    @staticmethod
    def _is_gate_statement(stmt: ir.Statement) -> bool:
        return isinstance(stmt, gate.stmts.Gate)

    def _is_clifford_gate(self, stmt: ir.Statement) -> bool:
        if isinstance(stmt, _CLIFFORD_GATES):
            return True

        if isinstance(stmt, gate.stmts.RotationGate):
            return self._is_clifford_rotation(stmt)

        if isinstance(stmt, gate.stmts.U3):
            return self._is_clifford_u3(stmt)

        return False

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        errors: list[ir.ValidationError] = []
        for stmt in method.callable_region.walk():
            if not self._is_gate_statement(stmt):
                continue

            if not self._is_clifford_gate(stmt):
                self._add_non_clifford_error(stmt, errors)

        return None, errors
