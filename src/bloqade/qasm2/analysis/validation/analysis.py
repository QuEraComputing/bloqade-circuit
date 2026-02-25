from typing import Any
from dataclasses import dataclass

from kirin import ir, types, interp
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward
from kirin.dialects import py, scf
from kirin.validation import ValidationPass
from kirin.analysis.forward import ForwardFrame

from bloqade.qasm2.types import CRegType
from bloqade.qasm2.dialects.core import CRegEq
from bloqade.qasm2.passes.unroll_if import DontLiftType


@dataclass
class _QASM2ValidationAnalysis(Forward[EmptyLattice]):
    keys = ["qasm2.main.validation"]

    lattice = EmptyLattice

    strict_if_conditions: bool = False

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

        if interp_.strict_if_conditions:
            self.__validate_if_condition(interp_, stmt)

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

    def __validate_if_condition(
        self, interp_: _QASM2ValidationAnalysis, stmt: scf.IfElse
    ):
        cond = stmt.cond
        cond_owner = cond.owner
        if not (isinstance(cond_owner, CRegEq) or isinstance(cond_owner, py.cmp.Eq)):
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt, f"Unpexpected condition type {type(cond_owner)}"
                ),
            )
            return

        lhs = cond_owner.lhs
        rhs = cond_owner.rhs

        one_side_is_creg = lhs.type.is_subseteq(CRegType) ^ rhs.type.is_subseteq(
            CRegType
        )
        one_side_is_int = lhs.type.is_subseteq(types.Int) ^ rhs.type.is_subseteq(
            types.Int
        )

        if not (one_side_is_int and one_side_is_creg):
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    f"Native QASM2 syntax only allows comparing an entire classical register to an integer, but got {lhs} == {rhs}",
                ),
            )

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


class QASM2ValidationStrictIfs(ValidationPass):
    def name(self) -> str:
        return "QASM2 validation (strict ifs)"

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        analysis = _QASM2ValidationAnalysis(method.dialects, strict_if_conditions=True)
        frame, _ = analysis.run(method)
        return frame, analysis.get_validation_errors()
