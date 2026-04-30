from typing import Any, Literal, TypeVar
from collections.abc import Mapping

from kirin.dialects import ilist
from kirin.lowering import wraps

from bloqade.types import Qubit

from . import stmts


@wraps(stmts.Depolarize)
def depolarize(p: float, qubits: ilist.IList[Qubit, Any]) -> None: ...


N = TypeVar("N", bound=int)
TwoQubitPauliProbabilities = (
    ilist.IList[float, Literal[15]] | list[float] | Mapping[str, float]
)


@wraps(stmts.Depolarize2)
def depolarize2(
    p: float, controls: ilist.IList[Qubit, N], targets: ilist.IList[Qubit, N]
) -> None: ...


@wraps(stmts.SingleQubitPauliChannel)
def single_qubit_pauli_channel(
    px: float, py: float, pz: float, qubits: ilist.IList[Qubit, Any]
) -> None: ...


@wraps(stmts.TwoQubitPauliChannel)
def two_qubit_pauli_channel(
    probabilities: TwoQubitPauliProbabilities,
    controls: ilist.IList[Qubit, N],
    targets: ilist.IList[Qubit, N],
) -> None: ...


@wraps(stmts.QubitLoss)
def qubit_loss(p: float, qubits: ilist.IList[Qubit, Any]) -> None: ...


@wraps(stmts.CorrelatedQubitLoss)
def correlated_qubit_loss(
    p: float, qubits: ilist.IList[ilist.IList[Qubit, N], Any]
) -> None: ...
