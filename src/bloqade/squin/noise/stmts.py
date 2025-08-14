from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist

from ._dialect import dialect
from ..op.types import OpType, NumOperators, MultiQubitPauliOpType


@statement
class NoiseChannel(ir.Statement):
    traits = frozenset({ir.Pure(), lowering.FromPythonCall()})
    result: ir.ResultValue = info.result(OpType)


@statement(dialect=dialect)
class PauliError(NoiseChannel):
    basis: ir.SSAValue = info.argument(MultiQubitPauliOpType)
    p: ir.SSAValue = info.argument(types.Float)


@statement(dialect=dialect)
class Depolarize(NoiseChannel):
    """
    Apply depolarize error to single qubit
    """

    p: ir.SSAValue = info.argument(types.Float)


@statement(dialect=dialect)
class Depolarize2(NoiseChannel):
    """
    Apply correlated depolarize error to two qubits

    This will apply one of the randomly chosen Pauli products:

    {IX, IY, IZ, XI, XX, XY, XZ, YI, YX, YY, YZ, ZI, ZX, ZY, ZZ}
    """

    p: ir.SSAValue = info.argument(types.Float)


@statement(dialect=dialect)
class SingleQubitPauliChannel(NoiseChannel):
    params: ir.SSAValue = info.argument(ilist.IListType[types.Float, types.Literal(3)])


@statement(dialect=dialect)
class TwoQubitPauliChannel(NoiseChannel):
    """
    This will apply one of the randomly chosen Pauli products:

    {IX, IY, IZ, XI, XX, XY, XZ, YI, YX, YY, YZ, ZI, ZX, ZY, ZZ}

    but the choice is weighed with the given probability.

    NOTE: the given parameters are ordered as given in the list above!
    """

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
