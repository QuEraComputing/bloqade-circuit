from typing import Any

from kirin import ir
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward
from kirin.validation import ValidationPass
from kirin.analysis.forward import ForwardFrame


class _CliffordAnalysis(Forward[EmptyLattice]):
    """Flags Squin gates that cannot be represented as Clifford gates in Stim."""

    keys = ("validate.clifford",)
    lattice = EmptyLattice

    def method_self(self, method: ir.Method) -> EmptyLattice:
        return self.lattice.bottom()

    def eval_fallback(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement
    ) -> tuple[EmptyLattice, ...]:
        return tuple(self.lattice.bottom() for _ in range(len(node.results)))

    def collect_errors(self, stmt: ir.Statement) -> None:
        self.add_validation_error(
            stmt,
            ir.ValidationError(
                stmt,
                f"Gate {stmt.name.upper()} is not a Clifford gate.",
            ),
        )


class CliffordValidation(ValidationPass):
    def name(self) -> str:
        return "Clifford Validation"

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        analysis = _CliffordAnalysis(method.dialects)
        frame, _ = analysis.run(method)
        return frame, analysis.get_validation_errors()
