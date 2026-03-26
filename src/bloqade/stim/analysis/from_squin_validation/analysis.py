from typing import Any

from kirin import ir, types, interp
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward
from kirin.dialects import scf, func
from kirin.validation import ValidationPass
from kirin.analysis.forward import ForwardFrame

from bloqade.qubit import stmts as qubit_stmts
from bloqade.squin import gate
from bloqade.types import MeasurementResultType
from bloqade.qubit._dialect import dialect as qubit_dialect

PauliGateType = (gate.stmts.X, gate.stmts.Y, gate.stmts.Z)


class _StimIfElseValidationAnalysis(Forward[EmptyLattice]):
    keys = ["stim.validate.from_squin"]

    lattice = EmptyLattice

    def method_self(self, method: ir.Method) -> EmptyLattice:
        return self.lattice.bottom()

    def eval_fallback(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement
    ) -> tuple[EmptyLattice, ...]:
        return tuple(self.lattice.bottom() for _ in range(len(node.results)))


@scf.dialect.register(key="stim.validate.from_squin")
class _ScfMethods(interp.MethodTable):

    @interp.impl(scf.IfElse)
    def if_else(
        self,
        interp_: _StimIfElseValidationAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: scf.IfElse,
    ):
        if stmt.cond.type == MeasurementResultType:
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    "MeasurementResult cannot be used directly as an IfElse condition "
                    "for rewriting to Stim IR. Use a predicate such as is_one instead.",
                ),
            )

        for child in stmt.walk(include_self=False):
            if isinstance(child, scf.IfElse):
                interp_.add_validation_error(
                    stmt,
                    ir.ValidationError(
                        stmt,
                        "Nested IfElse statements are not supported in rewriting to Stim IR.",
                    ),
                )
                break

        if stmt.else_body.blocks and not (
            len(stmt.else_body.blocks[0].stmts) == 1
            and isinstance(stmt.else_body.blocks[0].last_stmt, scf.Yield)
        ):
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    "IfElse statements with an else body are not supported in rewriting to Stim IR.",
                ),
            )

        for child in stmt.then_body.walk():
            if isinstance(child, gate.stmts.Gate) and not isinstance(
                child, PauliGateType
            ):
                interp_.add_validation_error(
                    stmt,
                    ir.ValidationError(
                        stmt,
                        f"Only Pauli gates (X, Y, Z) are allowed inside an scf.IfElse "
                        f"'then'-body for rewriting to Stim IR. Found: {type(child).__name__}",
                    ),
                )


@func.dialect.register(key="stim.validate.from_squin")
class _FuncMethods(interp.MethodTable):

    @interp.impl(func.Invoke)
    def invoke(
        self,
        interp_: _StimIfElseValidationAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: func.Invoke,
    ):
        # Walk callee body for unsupported statements (IsZero, IsLost, etc.)
        # without re-running the full validation (which would reject
        # non-None returns in helper functions).
        for child in stmt.callee.code.walk():
            if isinstance(child, qubit_stmts.IsZero):
                interp_.add_validation_error(
                    stmt,
                    ir.ValidationError(
                        child,
                        "is_zero predicate is not supported in rewriting to Stim IR. "
                        "Only the is_one predicate is supported.",
                    ),
                )
            elif isinstance(child, qubit_stmts.IsLost):
                interp_.add_validation_error(
                    stmt,
                    ir.ValidationError(
                        child,
                        "is_lost predicate is not supported in rewriting to Stim IR. "
                        "Only the is_one predicate is supported.",
                    ),
                )
        return (interp_.lattice.bottom(),)

    @interp.impl(func.Return)
    def return_stmt(
        self,
        interp_: _StimIfElseValidationAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: func.Return,
    ):
        if stmt.value.type != types.NoneType:
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    f"Kernel must return None for rewriting to Stim IR, "
                    f"but returns {stmt.value.type}.",
                ),
            )


@qubit_dialect.register(key="stim.validate.from_squin")
class _QubitMethods(interp.MethodTable):

    @interp.impl(qubit_stmts.IsZero)
    def is_zero(
        self,
        interp_: _StimIfElseValidationAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: qubit_stmts.IsZero,
    ):
        interp_.add_validation_error(
            stmt,
            ir.ValidationError(
                stmt,
                "is_zero predicate is not supported in rewriting to Stim IR. Only the is_one predicate is supported.",
            ),
        )

    @interp.impl(qubit_stmts.IsLost)
    def is_lost(
        self,
        interp_: _StimIfElseValidationAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: qubit_stmts.IsLost,
    ):
        interp_.add_validation_error(
            stmt,
            ir.ValidationError(
                stmt,
                "is_lost predicate is not supported in rewriting to Stim IR. Only the is_one predicate is supported.",
            ),
        )


class StimFromSquinValidation(ValidationPass):
    def name(self) -> str:
        return "Stim from Squin Validation"

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        analysis = _StimIfElseValidationAnalysis(method.dialects)
        frame, _ = analysis.run(method)
        return frame, analysis.get_validation_errors()
