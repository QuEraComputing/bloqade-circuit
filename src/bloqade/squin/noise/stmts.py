import typing

from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist

from bloqade.squin.op.types import OpType

from ._dialect import dialect


@statement
class NoiseChannel(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})


@statement
class UnitaryChannel(NoiseChannel):
    @property
    def operators(self) -> ilist.IList[ir.SSAValue, typing.Any]: ...

    @property
    def probabilities(self) -> ilist.IList[ir.SSAValue, typing.Any]: ...


@statement(dialect=dialect)
class PauliError(UnitaryChannel):
    basis: ir.SSAValue = info.argument(OpType)
    p: ir.SSAValue = info.argument(types.Float)
    result: ir.ResultValue = info.result(OpType)

    @property
    def operators(self):
        return ilist.IList([self.basis])

    @property
    def probabilities(self):
        return ilist.IList([self.p])


@statement(dialect=dialect)
class PPError(UnitaryChannel):
    """
    Pauli Product Error
    """

    op: ir.SSAValue = info.argument(OpType)
    p: ir.SSAValue = info.argument(types.Float)
    result: ir.ResultValue = info.result(OpType)


@statement(dialect=dialect)
class Depolarize(UnitaryChannel):
    """
    Apply n-qubit depolaize error to qubits
    NOTE For Stim, this can only accept 1 or 2 qubits
    """

    n_qubits: int = info.attribute(types.Int)
    p: ir.SSAValue = info.argument(types.Float)
    result: ir.ResultValue = info.result(OpType)


@statement(dialect=dialect)
class PauliChannel(UnitaryChannel):
    # NOTE:
    # 1-qubit 3 params px, py, pz
    # 2-qubit 15 params pix, piy, piz, pxi, pxx, pxy, pxz, pyi, pyx ..., pzz
    # TODO add validation for params (maybe during lowering via custom lower?)
    n_qubits: int = info.attribute()
    params: ir.SSAValue = info.argument(types.Tuple[types.Vararg(types.Float)])
    result: ir.ResultValue = info.result(OpType)


@statement(dialect=dialect)
class QubitLoss(NoiseChannel):
    # NOTE: qubit loss error (not supported by Stim)
    p: ir.SSAValue = info.argument(types.Float)
    result: ir.ResultValue = info.result(OpType)
