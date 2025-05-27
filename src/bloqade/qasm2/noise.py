from typing import Any

from kirin.dialects import ilist
from kirin.lowering import wraps

from .types import Qubit
from .dialects import noise
from .dialects.noise import (
    TwoRowZoneModel as TwoRowZoneModel,
    MoveNoiseModelABC as MoveNoiseModelABC,
)


@wraps(noise.AtomLossChannel)
def atom_loss_channel(qargs: ilist.IList[Qubit, Any] | list, *, prob: float) -> None:
    """Apply an atom loss channel to a list of qubits.

    Args:
        qargs (ilist.IList[Qubit, Any] | list): List of qubits to apply the noise to.
        prob (float): The loss probability.
    """
    ...


@wraps(noise.PauliChannel)
def pauli_channel(
    qargs: ilist.IList[Qubit, Any] | list, *, px: float, py: float, pz: float
) -> None:
    """Apply a Pauli channel to a list of qubits.

    Args:
        qargs (ilist.IList[Qubit, Any] | list): List of qubits to apply the noise to.
        px (float): Probability of X error.
        py (float): Probability of Y error.
        pz (float): Probability of Z error.
    """


@wraps(noise.CZPauliChannel)
def cz_pauli_channel(
    ctrls: ilist.IList[Qubit, Any] | list,
    qargs: ilist.IList[Qubit, Any] | list,
    *,
    px_ctrl: float,
    py_ctrl: float,
    pz_ctrl: float,
    px_qarg: float,
    py_qarg: float,
    pz_qarg: float,
    paired: bool,
) -> None:
    """Insert noise for a CZ gate with a Pauli channel on qubits.

    Args:
        ctrls: List of control qubits.
        qarg2: List of target qubits.
        px_ctrl: Probability of X error on control qubits.
        py_ctrl: Probability of Y error on control qubits.
        pz_ctrl: Probability of Z error on control qubits.
        px_qarg: Probability of X error on target qubits.
        py_qarg: Probability of Y error on target qubits.
        pz_qarg: Probability of Z error on target qubits.
        paired: If True, the noise is applied to both control and target qubits
            are not lost otherwise skip this error. If False Apply the noise on
            the whatever qubit is not lost.
    """
    ...
