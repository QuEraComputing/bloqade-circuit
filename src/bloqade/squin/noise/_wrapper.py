from kirin.lowering import wraps

from bloqade.squin.op.types import Op

from . import stmts


@wraps(stmts.PauliError)
def pauli_error(basis: Op, p: float) -> Op: ...


@wraps(stmts.PPError)
def pp_error(op: Op, p: float) -> Op: ...


@wraps(stmts.Depolarize)
def depolarize(n_qubits: int, p: float) -> Op: ...


@wraps(stmts.PauliChannel)
def pauli_channel(n_qubits: int, params: tuple[float, ...]) -> Op: ...


@wraps(stmts.QubitLoss)
def qubit_loss(p: float) -> Op: ...
