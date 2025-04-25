from kirin import ir, types
from kirin.decl import info, statement

from bloqade.squin.op.types import OpType

from ._dialect import dialect


@statement
class NoiseChannel(ir.Statement):
    pass


@statement(dialect=dialect)
class PauliError(NoiseChannel):
    name = "pauli_error"
    basis: ir.SSAValue = info.argument(OpType)
    p: ir.SSAValue = info.argument(types.Float)
    result: ir.ResultValue = info.result(OpType)


@statement(dialect=dialect)
class PPError(NoiseChannel):
    """
    Pauli Product Error
    """

    name = "pp_error"
    op: ir.SSAValue = info.argument(OpType)
    p: ir.SSAValue = info.argument(types.Float)
    result: ir.ResultValue = info.result(OpType)


@statement(dialect=dialect)
class Depolarize(NoiseChannel):
    """
    Apply n-qubit depolaize error to qubits
    NOTE For Stim, this can only accept 1 or 2 qubits
    """

    name = "depolarize"
    n_qubits: int = info.attribute(types.Int)
    p: ir.SSAValue = info.argument(types.Float)
    result: ir.ResultValue = info.result(OpType)


@statement(dialect=dialect)
class PauliChannel(NoiseChannel):
    # NOTE:
    # 1-qubit 3 params px, py, pz
    # 2-qubit 15 params pix, piy, piz, pxi, pxx, pxy, pxz, pyi, pyx ..., pzz
    # TODO add validation for params (maybe during lowering via custom lower?)
    name = "pauli_channel"
    n_qubits: int = info.attribute()
    params: ir.SSAValue = info.argument(types.Tuple[types.Vararg(types.Float)])
    result: ir.ResultValue = info.result(OpType)


@statement(dialect=dialect)
class QubitLoss(NoiseChannel):
    # NOTE: qubit loss error (not supported by Stim)
    name = "qubit_loss"
    p: ir.SSAValue = info.argument(types.Float)
    result: ir.ResultValue = info.result(OpType)
