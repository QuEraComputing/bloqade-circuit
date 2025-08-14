from typing import Literal

from kirin.dialects import ilist
from kirin.lowering import wraps

from bloqade.squin.op.types import Op, MultiQubitPauliOp

from . import stmts


@wraps(stmts.PauliError)
def pauli_error(basis: MultiQubitPauliOp, p: float) -> Op: ...


@wraps(stmts.Depolarize)
def depolarize(p: float) -> Op: ...


@wraps(stmts.Depolarize2)
def depolarize2(p: float) -> Op: ...


@wraps(stmts.SingleQubitPauliChannel)
def single_qubit_pauli_channel(
    params: ilist.IList[float, Literal[3]] | list[float],
) -> Op: ...


@wraps(stmts.TwoQubitPauliChannel)
def two_qubit_pauli_channel(
    params: ilist.IList[float, Literal[15]] | list[float],
) -> Op: ...


@wraps(stmts.QubitLoss)
def qubit_loss(p: float) -> Op: ...
