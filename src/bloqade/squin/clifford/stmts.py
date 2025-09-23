from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist

from bloqade.types import QubitType

from ._dialect import dialect

# N = types.TypeVar("N", bound=types.Int)


@statement
class SingleQubitGate(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, types.Any])


@statement(dialect=dialect)
class X(SingleQubitGate):
    pass


@statement(dialect=dialect)
class Y(SingleQubitGate):
    pass


@statement(dialect=dialect)
class Z(SingleQubitGate):
    pass


@statement(dialect=dialect)
class H(SingleQubitGate):
    pass


@statement(dialect=dialect)
class T(SingleQubitGate):
    pass


@statement
class SingleQubitNonHermitianGate(SingleQubitGate):
    adjoint: bool = info.attribute(default=False)


@statement(dialect=dialect)
class S(SingleQubitNonHermitianGate):
    pass


@statement(dialect=dialect)
class Sqrt_X(SingleQubitNonHermitianGate):
    pass


@statement(dialect=dialect)
class Sqrt_Y(SingleQubitNonHermitianGate):
    pass


@statement
class RotationGate(SingleQubitGate):
    angle: ir.SSAValue = info.argument(types.Float)


@statement(dialect=dialect)
class Rx(RotationGate):
    pass


@statement(dialect=dialect)
class Ry(RotationGate):
    pass


@statement(dialect=dialect)
class Rz(RotationGate):
    pass


# TODO: do we really need those statements?

# @statement(dialect=dialect)
# class U3(SingleQubitGate):
#     pass


# @statement(dialect=dialect)
# class Rot(SingleQubitGate):
#     pass


# @statement(dialect=dialect)
# class Shift(SingleQubitGate):
#     pass


N = types.TypeVar("N", bound=types.Int)


@statement
class ControlledGate(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    controls: ir.SSAValue = info.argument(ilist.IListType[QubitType, N])
    targets: ir.SSAValue = info.argument(ilist.IListType[QubitType, N])


@statement(dialect=dialect)
class CX(ControlledGate):
    pass


@statement(dialect=dialect)
class CY(ControlledGate):
    pass


@statement(dialect=dialect)
class CZ(ControlledGate):
    pass
