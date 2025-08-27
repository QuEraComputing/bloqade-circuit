from kirin import ir
from kirin.analysis import Forward, ForwardFrame

from ... import op
from .lattice import Unitary, UnitaryLattice
from ..hermitian import HermitianLattice, HermitianAnalysis


class UnitaryAnalysis(Forward):
    keys = ["squin.unitary"]
    lattice = UnitaryLattice
    hermitian_values: dict[ir.SSAValue, HermitianLattice] = dict()

    def run_method(self, method: ir.Method, args: tuple[UnitaryLattice, ...]):
        hermitian_frame, _ = HermitianAnalysis(method.dialects).run_analysis(method)
        self.hermitian_values.update(hermitian_frame.entries)
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)

    def eval_stmt_fallback(self, frame: ForwardFrame, stmt: ir.Statement):
        if not isinstance(stmt, op.stmts.Operator):
            return (self.lattice.bottom(),)

        if stmt.has_trait(op.traits.Unitary):
            return (Unitary(),)

        if (
            trait := stmt.get_trait(op.traits.MaybeUnitary)
        ) is not None and trait.is_unitary(stmt):
            return (Unitary(),)

        return (self.lattice.top(),)
