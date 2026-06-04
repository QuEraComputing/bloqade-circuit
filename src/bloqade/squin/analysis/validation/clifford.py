from typing import Any

from kirin import ir, interp
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward
from kirin.validation import ValidationPass
from kirin.analysis.forward import ForwardFrame

from bloqade.squin import gate
from bloqade.rewrite.passes import AggressiveUnroll


class _CliffordValidationAnalysis(Forward[EmptyLattice]):
    keys = ["squin.validate.clifford"]

    lattice = EmptyLattice

    def method_self(self, method: ir.Method) -> EmptyLattice:
        return self.lattice.bottom()

    def eval_fallback(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement
    ) -> tuple[EmptyLattice, ...]:
        return tuple(self.lattice.bottom() for _ in range(len(node.results)))


@gate.dialect.register(key="squin.validate.clifford")
class _GateMethods(interp.MethodTable):
    @interp.impl(gate.stmts.X)
    @interp.impl(gate.stmts.Y)
    @interp.impl(gate.stmts.Z)
    @interp.impl(gate.stmts.H)
    @interp.impl(gate.stmts.S)
    @interp.impl(gate.stmts.SqrtX)
    @interp.impl(gate.stmts.SqrtY)
    @interp.impl(gate.stmts.CX)
    @interp.impl(gate.stmts.CY)
    @interp.impl(gate.stmts.CZ)
    def clifford_gate(
        self,
        interp_: _CliffordValidationAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: gate.stmts.Gate,
    ):
        pass

    @interp.impl(gate.stmts.T)
    @interp.impl(gate.stmts.Rx)
    @interp.impl(gate.stmts.Ry)
    @interp.impl(gate.stmts.Rz)
    @interp.impl(gate.stmts.U3)
    @interp.impl(gate.stmts.PhasedXZ)
    def non_clifford_gate(
        self,
        interp_: _CliffordValidationAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: gate.stmts.Gate,
    ):
        interp_.add_validation_error(
            stmt,
            ir.ValidationError(
                stmt,
                f"Gate {type(stmt).__name__} is not supported by CliffordValidation.",
            ),
        )


class CliffordValidation(ValidationPass):
    def name(self) -> str:
        return "Squin Clifford Validation"

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        AggressiveUnroll(method.dialects).fixpoint(method)
        analysis = _CliffordValidationAnalysis(method.dialects)
        frame, _ = analysis.run(method)
        return frame, analysis.get_validation_errors()
