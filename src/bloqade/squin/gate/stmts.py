from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist

from bloqade.types import QubitType

from ._dialect import dialect


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


@statement
class SingleQubitNonHermitianGate(SingleQubitGate):
    adjoint: bool = info.attribute(default=False)


@statement(dialect=dialect)
class T(SingleQubitNonHermitianGate):
    pass


@statement(dialect=dialect)
class S(SingleQubitNonHermitianGate):
    pass


@statement(dialect=dialect)
class SqrtX(SingleQubitNonHermitianGate):
    pass


@statement(dialect=dialect)
class SqrtY(SingleQubitNonHermitianGate):
    pass


@statement
class RotationGate(ir.Statement):
    # NOTE: don't inherit from SingleQubitGate here so the wrapper doesn't have qubits as first arg
    traits = frozenset({lowering.FromPythonCall()})
    angle: ir.SSAValue = info.argument(types.Float)
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, types.Any])


@statement(dialect=dialect)
class Rx(RotationGate):
    pass


@statement(dialect=dialect)
class Ry(RotationGate):
    pass


@statement(dialect=dialect)
class Rz(RotationGate):
    pass


N = types.TypeVar("N", bound=types.Int)


@statement
class ControlledGate(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    controls: ir.SSAValue = info.argument(ilist.IListType[QubitType, N])
    targets: ir.SSAValue = info.argument(ilist.IListType[QubitType, N])


@statement(dialect=dialect)
class CX(ControlledGate):
    name = "cx"
    pass


@statement(dialect=dialect)
class CY(ControlledGate):
    name = "cy"
    pass


@statement(dialect=dialect)
class CZ(ControlledGate):
    name = "cz"
    pass


@statement(dialect=dialect)
class U3(ir.Statement):
    # NOTE: don't inherit from SingleQubitGate here so the wrapper doesn't have qubits as first arg
    traits = frozenset({lowering.FromPythonCall()})
    theta: ir.SSAValue = info.argument(types.Float)
    phi: ir.SSAValue = info.argument(types.Float)
    lam: ir.SSAValue = info.argument(types.Float)
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, types.Any])
