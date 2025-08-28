from kirin import interp
from kirin.analysis import ForwardFrame, const
from kirin.dialects import scf, func

from ... import op
from .lattice import Unitary, NotUnitary
from .analysis import UnitaryAnalysis
from ..hermitian import Hermitian, NotHermitian


@op.dialect.register(key="squin.unitary")
class UnitaryMethods(interp.MethodTable):
    @interp.impl(op.stmts.Control)
    @interp.impl(op.stmts.Adjoint)
    def simple_container(
        self,
        interp: UnitaryAnalysis,
        frame: ForwardFrame,
        stmt: op.stmts.Control | op.stmts.Adjoint,
    ):
        return (frame.get(stmt.op),)

    @interp.impl(op.stmts.Scale)
    def scale(self, interp: UnitaryAnalysis, frame: ForwardFrame, stmt: op.stmts.Scale):
        is_unitary = frame.get(stmt.op)

        # NOTE: need to check if the factor has absolute value squared of 1
        constant_value = stmt.factor.hints.get("const")
        if not isinstance(constant_value, const.Value):
            return (NotUnitary(),)

        num = constant_value.data
        if not isinstance(num, (float, int, bool, complex)):
            return (NotUnitary(),)

        if abs(num) ** 2 == 1:
            return (is_unitary.join(Unitary()),)

        return (NotUnitary(),)

    @interp.impl(op.stmts.Kron)
    @interp.impl(op.stmts.Mult)
    def binary_op(
        self,
        interp: UnitaryAnalysis,
        frame: ForwardFrame,
        stmt: op.stmts.Kron | op.stmts.Mult,
    ):
        return (frame.get(stmt.lhs).join(frame.get(stmt.rhs)),)

    @interp.impl(op.stmts.Rot)
    def rot(self, interp: UnitaryAnalysis, frame: ForwardFrame, stmt: op.stmts.Rot):
        if interp.hermitian_values.get(stmt.axis, NotHermitian()).is_equal(Hermitian()):
            return (Unitary(),)
        else:
            return (NotUnitary(),)


@scf.dialect.register(key="squin.unitary")
class ScfUnitaryMethods(scf.typeinfer.TypeInfer):
    pass


@func.dialect.register(key="squin.unitary")
class FuncUnitaryMethods(func.typeinfer.TypeInfer):
    pass
