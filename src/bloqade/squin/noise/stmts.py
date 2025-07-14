from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist

from bloqade.squin.op.types import OpType

from ._dialect import dialect
from ..op.types import NumOperators


@statement
class NoiseChannel(ir.Statement):
    traits = frozenset({ir.Pure(), lowering.FromPythonCall()})
    result: ir.ResultValue = info.result(OpType)


@statement(dialect=dialect)
class PauliError(NoiseChannel):
    basis: ir.SSAValue = info.argument(OpType)
    p: ir.SSAValue = info.argument(types.Float)


@statement(dialect=dialect)
class PPError(NoiseChannel):
    """
    Pauli Product Error
    """

    op: ir.SSAValue = info.argument(OpType)
    p: ir.SSAValue = info.argument(types.Float)


@statement(dialect=dialect)
class Depolarize(NoiseChannel):
    """
    Apply depolarize error to qubit
    """

    p: ir.SSAValue = info.argument(types.Float)


@statement(dialect=dialect)
class SingleQubitPauliChannel(NoiseChannel):
    params: ir.SSAValue = info.argument(ilist.IListType[types.Float, types.Literal(3)])


@statement(dialect=dialect)
class TwoQubitPauliChannel(NoiseChannel):
    params: ir.SSAValue = info.argument(ilist.IListType[types.Float, types.Literal(15)])


@statement(dialect=dialect)
class QubitLoss(NoiseChannel):
    # NOTE: qubit loss error (not supported by Stim)
    p: ir.SSAValue = info.argument(types.Float)


@statement(dialect=dialect)
class StochasticUnitaryChannel(ir.Statement):
    operators: ir.SSAValue = info.argument(ilist.IListType[OpType, NumOperators])
    probabilities: ir.SSAValue = info.argument(
        ilist.IListType[types.Float, NumOperators]
    )
    result: ir.ResultValue = info.result(OpType)
