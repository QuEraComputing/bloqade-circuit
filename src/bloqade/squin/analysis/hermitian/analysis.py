from kirin import ir
from kirin.analysis import Forward, ForwardFrame

from ... import op
from .lattice import Hermitian, HermitianLattice


class HermitianAnalysis(Forward):
    keys = ["squin.hermitian"]
    lattice = HermitianLattice

    def run_method(self, method: ir.Method, args: tuple[HermitianLattice, ...]):
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)

    def eval_stmt_fallback(self, frame: ForwardFrame, stmt: ir.Statement):
        if not isinstance(stmt, op.stmts.Operator):
            return (self.lattice.bottom(),)

        if stmt.has_trait(op.traits.Hermitian):
            return (Hermitian(),)

        if (
            trait := stmt.get_trait(op.traits.MaybeHermitian)
        ) is not None and trait.is_hermitian(stmt):
            return (Hermitian(),)

        return (self.lattice.top(),)
