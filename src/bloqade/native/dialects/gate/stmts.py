from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist

from bloqade.types import QubitType

from ._dialect import dialect

N = types.TypeVar("N")


@statement(dialect=dialect)
class CZ(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    controls: ir.SSAValue = info.argument(ilist.IListType[QubitType, N])
    targets: ir.SSAValue = info.argument(ilist.IListType[QubitType, N])


@statement(dialect=dialect)
class R(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    axis_angle: ir.SSAValue = info.argument(types.Float)
    rotation_angle: ir.SSAValue = info.argument(types.Float)
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, types.Any])


@statement(dialect=dialect)
class Rz(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    rotation_angle: ir.SSAValue = info.argument(types.Float)
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, types.Any])
