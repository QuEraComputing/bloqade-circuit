from kirin import ir, types, lowering
from kirin.decl import info, statement

from .types import OpType
from .number import NumberType
from .traits import Unitary, HasSites, FixedSites, MaybeUnitary
from ._dialect import dialect


@statement
class Operator(ir.Statement):
    result: ir.ResultValue = info.result(OpType)


@statement
class PrimitiveOp(Operator):
    pass


@statement
class CompositeOp(Operator):
    pass


@statement
class BinaryOp(CompositeOp):
    lhs: ir.SSAValue = info.argument(OpType)
    rhs: ir.SSAValue = info.argument(OpType)


@statement(dialect=dialect)
class Kron(BinaryOp):
    traits = frozenset({ir.Pure(), lowering.FromPythonCall(), MaybeUnitary()})
    is_unitary: bool = info.attribute(default=False)


@statement(dialect=dialect)
class Mult(BinaryOp):
    traits = frozenset({ir.Pure(), lowering.FromPythonCall(), MaybeUnitary()})
    is_unitary: bool = info.attribute(default=False)


@statement(dialect=dialect)
class Adjoint(CompositeOp):
    traits = frozenset({ir.Pure(), lowering.FromPythonCall(), MaybeUnitary()})
    is_unitary: bool = info.attribute(default=False)
    op: ir.SSAValue = info.argument(OpType)


@statement(dialect=dialect)
class Scale(CompositeOp):
    traits = frozenset({ir.Pure(), lowering.FromPythonCall(), MaybeUnitary()})
    is_unitary: bool = info.attribute(default=False)
    op: ir.SSAValue = info.argument(OpType)
    factor: ir.SSAValue = info.argument(NumberType)


@statement(dialect=dialect)
class Control(CompositeOp):
    traits = frozenset({ir.Pure(), lowering.FromPythonCall(), MaybeUnitary()})
    is_unitary: bool = info.attribute(default=False)
    op: ir.SSAValue = info.argument(OpType)
    n_controls: int = info.attribute()


@statement(dialect=dialect)
class Rot(CompositeOp):
    traits = frozenset({ir.Pure(), lowering.FromPythonCall(), Unitary()})
    axis: ir.SSAValue = info.argument(OpType)
    angle: ir.SSAValue = info.argument(types.Float)


@statement(dialect=dialect)
class Identity(CompositeOp):
    traits = frozenset({ir.Pure(), lowering.FromPythonCall(), Unitary(), HasSites()})
    sites: int = info.attribute()


@statement
class ConstantOp(PrimitiveOp):
    traits = frozenset(
        {ir.Pure(), lowering.FromPythonCall(), ir.ConstantLike(), FixedSites(1)}
    )


@statement
class ConstantUnitary(ConstantOp):
    traits = frozenset(
        {
            ir.Pure(),
            lowering.FromPythonCall(),
            ir.ConstantLike(),
            Unitary(),
            FixedSites(1),
        }
    )


@statement(dialect=dialect)
class U3(PrimitiveOp):
    """
    The rotation operator U3(theta, phi, lam).
    Note that we use the convention from the QASM2 specification, namely

    $$
    U_3(\theta, \phi, \lambda) = R_z(\phi) R_y(\theta) R_z(\lambda)
    $$
    """

    traits = frozenset({ir.Pure(), lowering.FromPythonCall(), Unitary(), FixedSites(1)})
    theta: ir.SSAValue = info.argument(types.Float)
    phi: ir.SSAValue = info.argument(types.Float)
    lam: ir.SSAValue = info.argument(types.Float)


@statement(dialect=dialect)
class PhaseOp(PrimitiveOp):
    """
    A phase operator.

    $$
    PhaseOp(\theta) = e^{i \theta} I
    $$
    """

    traits = frozenset({ir.Pure(), lowering.FromPythonCall(), Unitary(), FixedSites(1)})
    theta: ir.SSAValue = info.argument(types.Float)


@statement(dialect=dialect)
class ShiftOp(PrimitiveOp):
    """
    A phase shift operator.

    $$
    Shift(\theta) = \\begin{bmatrix} 1 & 0 \\\\ 0 & e^{i \\theta} \\end{bmatrix}
    $$
    """

    traits = frozenset({ir.Pure(), lowering.FromPythonCall(), Unitary(), FixedSites(1)})
    theta: ir.SSAValue = info.argument(types.Float)


@statement(dialect=dialect)
class Reset(PrimitiveOp):
    """
    Reset operator for qubits or wires.
    """

    traits = frozenset({ir.Pure(), lowering.FromPythonCall(), FixedSites(1)})


@statement(dialect=dialect)
class ResetToOne(PrimitiveOp):
    """
    Reset qubits to the one state. Mainly needed to accommodate cirq's GeneralizedAmplitudeDampingChannel
    """

    traits = frozenset({ir.Pure(), lowering.FromPythonCall(), FixedSites(1)})


@statement
class CliffordOp(ConstantUnitary):
    pass


@statement
class PauliOp(CliffordOp):
    pass


@statement(dialect=dialect)
class PauliString(ConstantUnitary):
    traits = frozenset({ir.Pure(), lowering.FromPythonCall(), Unitary(), HasSites()})
    string: str = info.attribute()

    def verify(self) -> None:
        if not set("XYZ").issuperset(self.string):
            raise ValueError(
                f"Invalid Pauli string: {self.string}. Must be a combination of 'X', 'Y', and 'Z'."
            )


@statement(dialect=dialect)
class X(PauliOp):
    pass


@statement(dialect=dialect)
class Y(PauliOp):
    pass


@statement(dialect=dialect)
class Z(PauliOp):
    pass


@statement(dialect=dialect)
class SqrtX(ConstantUnitary):
    pass


@statement(dialect=dialect)
class SqrtY(ConstantUnitary):
    pass


# NOTE no SqrtZ since its equal to S


@statement(dialect=dialect)
class H(ConstantUnitary):
    pass


@statement(dialect=dialect)
class S(ConstantUnitary):
    pass


@statement(dialect=dialect)
class T(ConstantUnitary):
    pass


@statement(dialect=dialect)
class P0(ConstantOp):
    """
    The $P_0$ projection operator.

    $$
    P0 = \\begin{bmatrix} 1 & 0 \\\\ 0 & 0 \\end{bmatrix}
    $$
    """

    pass


@statement(dialect=dialect)
class P1(ConstantOp):
    """
    The $P_1$ projection operator.

    $$
    P1 = \\begin{bmatrix} 0 & 0 \\\\ 0 & 1 \\end{bmatrix}
    $$
    """

    pass


@statement(dialect=dialect)
class Sn(ConstantOp):
    """
    $S_{-}$ operator.

    $$
    Sn = \\frac{1}{2} (S_x - i S_y) = \\frac{1}{2} \\begin{bmatrix} 0 & 0 \\\\ 1 & 0 \\end{bmatrix}
    $$
    """

    pass


@statement(dialect=dialect)
class Sp(ConstantOp):
    """
    $S_{+}$ operator.

    $$
    Sp = \\frac{1}{2} (S_x + i S_y) = \\frac{1}{2}\\begin{bmatrix} 0 & 1 \\\\ 0 & 0 \\end{bmatrix}
    $$
    """

    pass
