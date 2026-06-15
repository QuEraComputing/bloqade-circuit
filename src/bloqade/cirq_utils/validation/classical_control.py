from typing import Any

from kirin import ir, interp
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward
from kirin.dialects import scf
from kirin.validation import ValidationPass
from kirin.analysis.forward import ForwardFrame

from bloqade.cirq_utils.classical_control import (
    is_empty_else,
    get_single_gate,
    is_is_lost_condition,
    is_single_qubit_measure,
    parse_classical_if_condition,
)


class _CirqClassicalControlValidationAnalysis(Forward[EmptyLattice]):
    """Forward analysis that validates IfElse patterns for cirq emission."""

    keys = ("cirq.validate.classical_control",)

    lattice = EmptyLattice

    def method_self(self, method: ir.Method) -> EmptyLattice:
        return EmptyLattice.bottom()

    def eval_fallback(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement
    ) -> tuple[EmptyLattice, ...]:
        return tuple(self.lattice.bottom() for _ in range(len(node.results)))


@scf.dialect.register(key="cirq.validate.classical_control")
class _ScfMethods(interp.MethodTable):

    @interp.impl(scf.IfElse)
    def if_else(
        self,
        interp_: _CirqClassicalControlValidationAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: scf.IfElse,
    ):
        if is_is_lost_condition(stmt.cond):
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    "IfElse condition based on is_lost has no Cirq equivalent and "
                    "cannot be emitted as a classical control.",
                ),
            )
            return

        condition = parse_classical_if_condition(stmt.cond)
        if condition is None:
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    "IfElse condition must compare a single measurement result to "
                    "0 or 1 using ==, !=, is_one, or is_zero.",
                ),
            )
            return

        if not is_single_qubit_measure(condition.measure):
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    "IfElse classical control requires a condition based on a single "
                    "qubit measurement.",
                ),
            )

        if not is_empty_else(stmt):
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    "IfElse statements with a non-empty else body cannot be emitted "
                    "as cirq classical control.",
                ),
            )

        if get_single_gate(stmt) is None:
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    "IfElse then-body must contain exactly one gate operation for "
                    "cirq classical control emission.",
                ),
            )

        for child in stmt.then_body.walk():
            if child is stmt:
                continue
            if isinstance(child, scf.IfElse):
                interp_.add_validation_error(
                    stmt,
                    ir.ValidationError(
                        stmt,
                        "Nested IfElse statements cannot be emitted as cirq classical "
                        "control.",
                    ),
                )
                break


class CirqClassicalControlValidation(ValidationPass):
    """Validate squin IfElse statements before cirq classical control emission."""

    def name(self) -> str:
        """Return the validation pass name."""
        return "Cirq Classical Control Validation"

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        """Run classical control validation on ``method``."""
        analysis = _CirqClassicalControlValidationAnalysis(method.dialects)
        frame, _ = analysis.run(method)
        return frame, analysis.get_validation_errors()
