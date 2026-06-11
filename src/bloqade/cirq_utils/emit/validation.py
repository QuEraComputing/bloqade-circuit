from typing import Any

from kirin import ir, interp
from kirin.dialects import ilist, scf
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward
from kirin.validation import ValidationPass
from kirin.analysis.forward import ForwardFrame

from bloqade.squin import gate
from bloqade.qubit import stmts as qubit

from .classical_control import get_measurement_condition


class _CirqEmissionValidationAnalysis(Forward[EmptyLattice]):
    keys = ["cirq.emit.validation"]
    lattice = EmptyLattice

    def method_self(self, method: ir.Method) -> EmptyLattice:
        return self.lattice.bottom()

    def eval_fallback(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement
    ) -> tuple[EmptyLattice, ...]:
        return tuple(self.lattice.bottom() for _ in range(len(node.results)))


def _body_stmts(region: ir.Region) -> list[ir.Statement]:
    return list(region.stmts())


def _has_empty_else(stmt: scf.IfElse) -> bool:
    else_stmts = _body_stmts(stmt.else_body)
    return len(else_stmts) == 0 or (
        len(else_stmts) == 1 and isinstance(else_stmts[0], scf.Yield)
    )


def _validate_then_body(
    analysis: _CirqEmissionValidationAnalysis, stmt: scf.IfElse
) -> None:
    body_stmts = [
        child
        for child in _body_stmts(stmt.then_body)
        if not isinstance(child, scf.Yield)
    ]
    gate_stmts = [child for child in body_stmts if isinstance(child, gate.stmts.Gate)]

    if len(gate_stmts) != 1:
        analysis.add_validation_error(
            stmt,
            ir.ValidationError(
                stmt,
                "Cirq if emission requires the then body to contain exactly "
                "one gate operation.",
            ),
        )

    for child in body_stmts:
        if isinstance(child, (gate.stmts.Gate, ilist.New)):
            continue
        analysis.add_validation_error(
            stmt,
            ir.ValidationError(
                stmt,
                "Cirq if emission supports only one gate operation in the then body.",
            ),
        )
        break


@scf.dialect.register(key="cirq.emit.validation")
class _ScfMethods(interp.MethodTable):
    @interp.impl(scf.IfElse)
    def if_else(
        self,
        analysis: _CirqEmissionValidationAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: scf.IfElse,
    ):
        if get_measurement_condition(stmt.cond) is None:
            analysis.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    "Cirq if emission supports conditions comparing one "
                    "measurement result with True, False, 1, or 0.",
                ),
            )

        if not _has_empty_else(stmt):
            analysis.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    "Cirq if emission requires the else body to be empty.",
                ),
            )

        _validate_then_body(analysis, stmt)

        for child in stmt.walk(include_self=False):
            if isinstance(child, scf.IfElse):
                analysis.add_validation_error(
                    stmt,
                    ir.ValidationError(
                        stmt,
                        "Nested if statements are not supported by Cirq emission.",
                    ),
                )
                break
            if isinstance(child, (qubit.Measure, qubit.Reset, qubit.New)):
                analysis.add_validation_error(
                    stmt,
                    ir.ValidationError(
                        stmt,
                        "Cirq if emission supports only gate operations in the then body.",
                    ),
                )
                break


class CirqEmissionValidation(ValidationPass):
    def name(self) -> str:
        return "Cirq Emission Validation"

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        analysis = _CirqEmissionValidationAnalysis(method.dialects)
        frame, _ = analysis.run(method)
        return frame, analysis.get_validation_errors()
