from typing import Literal

from kirin.dialects import ilist
from kirin.lowering import wraps

from bloqade.squin.op.types import Op

from . import stmts


@wraps(stmts.PauliError)
def pauli_error(basis: Op, p: float) -> Op: ...


@wraps(stmts.PPError)
def pp_error(op: Op, p: float) -> Op: ...


@wraps(stmts.Depolarize)
def depolarize(p: float) -> Op: ...


@wraps(stmts.SingleQubitPauliChannel)
def single_qubit_pauli_channel(
    params: ilist.IList[float, Literal[3]] | list[float] | tuple[float, float, float],
) -> Op: ...


@wraps(stmts.TwoQubitPauliChannel)
def two_qubit_pauli_channel(
    params: ilist.IList[float, Literal[15]] | list[float] | tuple[float, ...],
) -> Op: ...


@wraps(stmts.QubitLoss)
def qubit_loss(p: float) -> Op: ...
