from typing import Any

from kirin import ir, interp
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward
from kirin.dialects import func
from kirin.validation import ValidationPass
from kirin.analysis.forward import ForwardFrame

from bloqade.squin import gate
from bloqade.rewrite.passes import AggressiveUnroll


class _CliffordValidationAnalysis(Forward[EmptyLattice]):
    """Reject SQUIN kernels that contain syntactically non-Clifford gates."""

    keys = ["validate.clifford"]
    lattice = EmptyLattice

    def method_self(self, method: ir.Method) -> EmptyLattice:
        return self.lattice.bottom()

    def eval_fallback(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement
    ) -> tuple[EmptyLattice, ...]:
        return tuple(self.lattice.bottom() for _ in range(len(node.results)))

    def collect_error(self, stmt: ir.Statement) -> None:
        self.add_validation_error(
            stmt,
            ir.ValidationError(
                stmt,
                f"Gate {stmt.name.upper()} is not a Clifford gate.",
            ),
        )


@gate.dialect.register(key="validate.clifford")
class _GateMethods(interp.MethodTable):
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
    ) -> None:
        interp_.collect_error(stmt)


def _unroll_method(method: ir.Method) -> ir.Method:
    symbol_op_trait = method.code.get_trait(ir.SymbolOpInterface)
    signature_trait = method.code.get_trait(ir.HasSignature)

    if symbol_op_trait is None or signature_trait is None:
        return method

    sym_name = symbol_op_trait.get_sym_name(method.code).unwrap()
    unrolled_func = func.Function(
        sym_name=sym_name,
        body=method.callable_region.clone(),
        signature=signature_trait.get_signature(method.code),
    )
    unrolled_method = ir.Method(
        dialects=method.dialects,
        code=unrolled_func,
        sym_name=sym_name,
    )

    AggressiveUnroll(unrolled_method.dialects).fixpoint(unrolled_method)
    return unrolled_method


class CliffordValidation(ValidationPass):
    def name(self) -> str:
        return "Clifford Validation"

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        method = _unroll_method(method)
        analysis = _CliffordValidationAnalysis(method.dialects)
        frame, _ = analysis.run(method)
        return frame, analysis.get_validation_errors()
