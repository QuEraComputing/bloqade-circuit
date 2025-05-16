from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist

from bloqade.squin.op.types import OpType

from ._dialect import dialect
from ..op.types import NumOperators


@statement
class NoiseChannel(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
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
    Apply n-qubit depolarize error to qubits
    NOTE For Stim, this can only accept 1 or 2 qubits
    """

    n_qubits: int = info.attribute(types.Int)
    p: ir.SSAValue = info.argument(types.Float)


@statement(dialect=dialect)
class PauliChannel(NoiseChannel):
    # NOTE:
    # 1-qubit 3 params px, py, pz
    # 2-qubit 15 params pix, piy, piz, pxi, pxx, pxy, pxz, pyi, pyx ..., pzz
    # TODO add validation for params (maybe during lowering via custom lower?)
    n_qubits: int = info.attribute()
    params: ir.SSAValue = info.argument(types.Tuple[types.Vararg(types.Float)])


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
