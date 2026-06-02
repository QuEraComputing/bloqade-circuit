from typing import Any
from dataclasses import dataclass

from kirin import ir
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward
from kirin.validation import ValidationPass
from kirin.analysis.forward import ForwardFrame


class _CliffordValidationAnalysis(Forward[EmptyLattice]):
    """Validation analysis that rejects non-Clifford SQUIN gate statements."""

    keys = ("validate.clifford",)
    lattice = EmptyLattice

    def eval_fallback(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement
    ) -> tuple[EmptyLattice, ...]:
        return tuple(EmptyLattice.bottom() for _ in node.results)

    def method_self(self, method: ir.Method) -> EmptyLattice:
        return EmptyLattice.bottom()

    def collect_error(self, stmt: ir.Statement) -> None:
        self.add_validation_error(
            stmt,
            ir.ValidationError(
                stmt,
                f"Gate {type(stmt).__name__} is not a Clifford gate.",
            ),
        )


@dataclass
class CliffordValidation(ValidationPass):
    def name(self) -> str:
        return "Clifford Gate Validation"

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        analysis = _CliffordValidationAnalysis(method.dialects)
        frame, _ = analysis.run(
            method, *(EmptyLattice.bottom() for _ in range(len(method.args) - 1))
        )
        return frame, analysis.get_validation_errors()
