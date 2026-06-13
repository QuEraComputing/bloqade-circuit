from typing import Any

from kirin import ir
from kirin.analysis import CallGraph
from kirin.validation import ValidationPass

from bloqade.squin import gate


_CLIFFORD_GATE_TYPES = (
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


def _gate_name(stmt: gate.stmts.Gate) -> str:
    return type(stmt).__name__


class CliffordValidation(ValidationPass):
    """Validate that a SQUIN kernel only contains Clifford gates.

    This pass walks the method's call graph so kernels using the public SQUIN
    wrappers, such as ``squin.t(q[0])``, are checked without requiring callers
    to manually inline the kernel first.
    """

    def name(self) -> str:
        return "Clifford Validation"

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        errors: list[ir.ValidationError] = []

        call_graph = CallGraph(method)
        methods = set(call_graph.edges.keys())
        methods.add(method)

        for current_method in methods:
            for stmt in current_method.callable_region.walk():
                if not isinstance(stmt, gate.stmts.Gate):
                    continue

                if isinstance(stmt, _CLIFFORD_GATE_TYPES):
                    continue

                errors.append(
                    ir.ValidationError(
                        stmt,
                        f"Gate {_gate_name(stmt)} is not allowed in a Clifford-only SQUIN kernel.",
                    )
                )

        return method, errors
