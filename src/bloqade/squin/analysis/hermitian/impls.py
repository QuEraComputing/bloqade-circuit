from kirin import types, interp
from kirin.analysis import ForwardFrame
from kirin.dialects import scf, func

from ... import op
from .lattice import Hermitian, NotHermitian
from .analysis import HermitianAnalysis


@op.dialect.register(key="squin.hermitian")
class HermitianMethods(interp.MethodTable):
    @interp.impl(op.stmts.Control)
    @interp.impl(op.stmts.Adjoint)
    def simple_container(
        self,
        interp: HermitianAnalysis,
        frame: ForwardFrame,
        stmt: op.stmts.Control | op.stmts.Adjoint,
    ):
        return (frame.get(stmt.op),)

    @interp.impl(op.stmts.Scale)
    def scale(
        self, interp: HermitianAnalysis, frame: ForwardFrame, stmt: op.stmts.Scale
    ):
        is_hermitian = frame.get(stmt.op)

        # NOTE: need to check if the factor is a real number
        if stmt.factor.type.is_subseteq(types.Float | types.Int | types.Bool):
            return (is_hermitian.join(Hermitian()),)

        return (NotHermitian(),)

    @interp.impl(op.stmts.Kron)
    def kron(self, interp: HermitianAnalysis, frame: ForwardFrame, stmt: op.stmts.Kron):
        is_hermitian = frame.get(stmt.lhs).join(frame.get(stmt.rhs))
        return (is_hermitian,)

    @interp.impl(op.stmts.Mult)
    def mult(self, interp: HermitianAnalysis, frame: ForwardFrame, stmt: op.stmts.Mult):
        # NOTE: this could be smarter here and check whether lhs == adjoint(rhs)
        if stmt.lhs != stmt.rhs:
            return (NotHermitian(),)

        return (frame.get(stmt.lhs),)


@scf.dialect.register(key="squin.hermitian")
class ScfHermitianMethods(scf.typeinfer.TypeInfer):
    pass


@func.dialect.register(key="squin.hermitian")
class FuncHermitianMethods(func.typeinfer.TypeInfer):
    pass
