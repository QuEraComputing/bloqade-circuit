from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist

from bloqade.squin import qubit

from ._dialect import dialect

N = types.TypeVar("N")


@statement(dialect=dialect)
class CZ(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    ctrls: ir.SSAValue = info.argument(ilist.IListType[qubit.QubitType, N])
    qargs: ir.SSAValue = info.argument(ilist.IListType[qubit.QubitType, N])


@statement(dialect=dialect)
class R(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    inputs: ir.SSAValue = info.argument(ilist.IListType[qubit.QubitType, types.Any])
    axis_angle: ir.SSAValue = info.argument(types.Float)
    rotation_angle: ir.SSAValue = info.argument(types.Float)


@statement(dialect=dialect)
class Rz(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    inputs: ir.SSAValue = info.argument(ilist.IListType[qubit.QubitType, types.Any])
    rotation_angle: ir.SSAValue = info.argument(types.Float)
