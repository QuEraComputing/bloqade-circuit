from kirin import ir, types, interp
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward, ForwardFrame, const
from kirin.dialects import scf, func

from .. import op


class HermitianAnalysis(Forward):
    keys = ["squin.hermitian"]
    lattice = EmptyLattice

    def run_method(self, method: ir.Method, args: tuple[EmptyLattice, ...]):
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)

    def eval_stmt_fallback(
        self, frame: ForwardFrame, stmt: ir.Statement
    ) -> tuple[bool] | None:
        if not isinstance(stmt, op.stmts.Operator):
            return

        if stmt.has_trait(op.traits.Hermitian):
            return (True,)

        if (trait := stmt.get_trait(op.traits.MaybeHermitian)) is not None:
            return (trait.is_hermitian(stmt),)

        return (False,)


class UnitaryAnalysis(Forward):
    keys = ["squin.unitary"]
    lattice = EmptyLattice
    hermitian_values: dict[ir.SSAValue, bool | None] = dict()

    def run_method(self, method: ir.Method, args: tuple[EmptyLattice, ...]):
        hermitian_frame, _ = HermitianAnalysis(method.dialects).run_analysis(method)
        self.hermitian_values.update(hermitian_frame.entries)
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)

    def eval_stmt_fallback(
        self, frame: ForwardFrame, stmt: ir.Statement
    ) -> tuple[bool] | None:
        if not isinstance(stmt, op.stmts.Operator):
            return

        if stmt.has_trait(op.traits.Unitary):
            return (True,)

        if (trait := stmt.get_trait(op.traits.MaybeUnitary)) is not None:
            return (trait.is_unitary(stmt),)

        return (False,)


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
        if not frame.get(stmt.op):
            # NOTE: definitely not hermitian
            return (False,)

        # NOTE: need to check if the factor is a real number
        return (stmt.factor.type.is_subseteq(types.Float | types.Int | types.Bool),)

    @interp.impl(op.stmts.Kron)
    def kron(self, interp: HermitianAnalysis, frame: ForwardFrame, stmt: op.stmts.Kron):
        is_hermitian = frame.get(stmt.lhs) and frame.get(stmt.rhs)
        return (is_hermitian,)

    @interp.impl(op.stmts.PauliString)
    def pauli_string(
        self, interp: HermitianAnalysis, frame: ForwardFrame, stmt: op.stmts.PauliString
    ):
        reversed_string = list(reversed(stmt.string))
        return (reversed_string == list(stmt.string),)

    @interp.impl(op.stmts.Mult)
    def mult(self, interp: HermitianAnalysis, frame: ForwardFrame, stmt: op.stmts.Mult):
        # NOTE: this could be smarter here and check whether lhs == adjoint(rhs)
        return (stmt.lhs == stmt.rhs and frame.get(stmt.lhs),)


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
        if not frame.get(stmt.op):
            # NOTE: definitely not hermitian
            return (False,)

        # NOTE: need to check if the factor has absolute value squared of 1
        constant_value = stmt.factor.hints.get("const")
        if not isinstance(constant_value, const.Value):
            return (False,)

        num = constant_value.data
        try:
            abs2 = abs(num) ** 2
        except ValueError:
            # not a number for which we can check?
            return (False,)

        return (abs2 == 1,)

    @interp.impl(op.stmts.Kron)
    @interp.impl(op.stmts.Mult)
    def binary_op(
        self,
        interp: UnitaryAnalysis,
        frame: ForwardFrame,
        stmt: op.stmts.Kron | op.stmts.Mult,
    ):
        return (frame.get(stmt.lhs) and frame.get(stmt.rhs),)

    @interp.impl(op.stmts.Rot)
    def rot(self, interp: UnitaryAnalysis, frame: ForwardFrame, stmt: op.stmts.Rot):
        return (interp.hermitian_values.get(stmt.axis, False),)


@scf.dialect.register(key="squin.hermitian")
class ScfHermitianMethods(scf.typeinfer.TypeInfer):
    pass


@func.dialect.register(key="squin.hermitian")
class FuncHermitianMethods(func.typeinfer.TypeInfer):
    pass


@scf.dialect.register(key="squin.unitary")
class ScfUnitaryMethods(scf.typeinfer.TypeInfer):
    pass


@func.dialect.register(key="squin.unitary")
class FuncUnitaryMethods(func.typeinfer.TypeInfer):
    pass
