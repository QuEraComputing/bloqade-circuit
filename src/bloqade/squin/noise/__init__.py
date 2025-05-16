# Put all the proper wrappers here

from kirin.lowering import wraps as _wraps

from bloqade.squin.op.types import Op

from . import stmts as stmts
from ._dialect import dialect as dialect


@_wraps(stmts.PauliError)
def pauli_error(basis: Op, p: float) -> Op: ...


@_wraps(stmts.PPError)
def pp_error(op: Op, p: float) -> Op: ...


@_wraps(stmts.Depolarize)
def depolarize(n_qubits: int, p: float) -> Op: ...


# TODO: add some syntax sugar?
@_wraps(stmts.SingleQubitPauliChannel)
def single_qubit_pauli_channel(params: tuple[float, float, float]) -> Op: ...


@_wraps(stmts.TwoQubitPauliChannel)
def two_qubit_pauli_channel(params: tuple[float, ...]) -> Op: ...


@_wraps(stmts.QubitLoss)
def qubit_loss(p: float) -> Op: ...
