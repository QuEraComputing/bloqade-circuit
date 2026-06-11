from __future__ import annotations

from typing import Any

import numpy as np
from kirin import ir, rewrite
from kirin.analysis import CallGraph
from kirin.dialects import py
from kirin.validation import ValidationPass

from bloqade.squin import gate
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.rewrite.passes.callgraph import ReplaceMethods
from bloqade.squin.rewrite.U3_to_clifford import SquinU3ToClifford

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
    return np.isclose(quarter_turns, round(quarter_turns))


def _is_clifford_rotation(stmt: gate.stmts.RotationGate) -> bool:
    return _is_quarter_turn(stmt.angle)


def _is_clifford_u3(stmt: gate.stmts.U3) -> bool:
    return bool(SquinU3ToClifford().decompose_U3_gates(stmt))


def _is_clifford_phased_xz(stmt: gate.stmts.PhasedXZ) -> bool:
    # PhasedXZ is Rz(-axis_phase) Rx(x) Rz(axis_phase + z). Requiring all
    # exposed turn parameters to be quarter-turns is conservative and keeps the
    # validation pass non-mutating.
    return all(
        _is_quarter_turn(angle)
        for angle in (stmt.x_exponent, stmt.z_exponent, stmt.axis_phase_exponent)
    )


def _is_clifford_gate(stmt: gate.stmts.Gate) -> bool:
    if isinstance(stmt, _CLIFFORD_GATES):
        return True
    if isinstance(stmt, gate.stmts.RotationGate):
        return _is_clifford_rotation(stmt)
    if isinstance(stmt, gate.stmts.U3):
        return _is_clifford_u3(stmt)
    if isinstance(stmt, gate.stmts.PhasedXZ):
        return _is_clifford_phased_xz(stmt)
    return False


def _clone_call_graph(method: ir.Method) -> ir.Method:
    cloned_methods = {}
    call_graph = CallGraph(method)
    methods = set(call_graph.edges.keys())
    methods.update(sum(map(tuple, call_graph.defs.values()), ()))
    methods.add(method)

    for original_method in methods:
        cloned_methods[original_method] = original_method.similar()

    for cloned_method in cloned_methods.values():
        rewrite.Walk(ReplaceMethods(cloned_methods)).rewrite(cloned_method.code)

    return cloned_methods[method]


class CliffordValidation(ValidationPass):
    """Validate that a SQUIN kernel contains only Clifford gates."""

    def name(self) -> str:
        """Return the validation pass name."""
        return "Clifford Validation"

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        """Run Clifford-only validation for a SQUIN method."""
        errors: list[ir.ValidationError] = []
        canonical_method = _clone_call_graph(method)

        AggressiveUnroll(canonical_method.dialects).fixpoint(canonical_method)

        for stmt in canonical_method.callable_region.walk():
            if not isinstance(stmt, gate.stmts.Gate):
                continue
            if _is_clifford_gate(stmt):
                continue

            errors.append(
                ir.ValidationError(
                    stmt,
                    f"Non-Clifford gate {type(stmt).__name__} is not allowed "
                    "in a Clifford-only SQUIN kernel.",
                )
            )

        return method, errors
