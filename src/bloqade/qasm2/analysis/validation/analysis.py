from typing import Any

from kirin import ir, interp
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward
from kirin.dialects import scf
from kirin.validation import ValidationPass
from kirin.analysis.forward import ForwardFrame

from bloqade.qasm2.passes.unroll_if import DontLiftType


class _QASM2ValidationAnalysis(Forward[EmptyLattice]):
    keys = ["qasm2.main.validation"]

    lattice = EmptyLattice

    def method_self(self, method: ir.Method) -> EmptyLattice:
        return self.lattice.bottom()

    def eval_fallback(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement
    ) -> tuple[EmptyLattice, ...]:
        return tuple(self.lattice.bottom() for _ in range(len(node.results)))


@scf.dialect.register(key="qasm2.main.validation")
class __ScfMethods(interp.MethodTable):

    @interp.impl(scf.IfElse)
    def if_else(
        self,
        interp_: _QASM2ValidationAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: scf.IfElse,
    ):

        # TODO: stmt.condition has to be based off a measurement

        if len(stmt.then_body.blocks) > 1:
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    "Only single block is allowed in the then-body of an if-else statement!",
                ),
            )

        then_stmts = list(stmt.then_body.stmts())
        if len(then_stmts) > 2:
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    "Only single statements are allowed inside the then-body of an if-else statement!",
                ),
            )

        if not isinstance(then_stmts[0], DontLiftType):
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt, f"Statement {then_stmts[0]} not allowed inside if clause!"
                ),
            )

        self.__validate_empty_yield(interp_, then_stmts[-1])

        if len(stmt.else_body.blocks) > 1:
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    "Only single block is allowed in the else-body of an if-else statement!",
                ),
            )

        else_stmts = list(stmt.else_body.stmts())
        if len(else_stmts) > 1:
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(stmt, "Non-empty else is not allowed in QASM2!"),
            )

        self.__validate_empty_yield(interp_, else_stmts[-1])

    def __validate_empty_yield(
        self, interp_: _QASM2ValidationAnalysis, stmt: ir.Statement
    ):
        if not isinstance(stmt, scf.Yield):
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt, f"Expected scf.Yield terminator in if clause, got {stmt}"
                ),
            )
        elif len(stmt.values) > 0:
            interp_.add_validation_error(
                stmt, ir.ValidationError(stmt, "Cannot yield values from if statement!")
            )

    @interp.impl(scf.For)
    def for_loop(
        self,
        interp_: _QASM2ValidationAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: scf.For,
    ):
        interp_.add_validation_error(
            stmt, ir.ValidationError(stmt, "Loops not supported in QASM2!")
        )


class QASM2Validation(ValidationPass):
    def name(self) -> str:
        return "QASM2 validation"

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        analysis = _QASM2ValidationAnalysis(method.dialects)
        frame, _ = analysis.run(method)
        return frame, analysis.get_validation_errors()
