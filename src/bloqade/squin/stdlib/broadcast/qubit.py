from typing import Any

from kirin.dialects import ilist

from bloqade.types import Qubit

from ...qubit import _interface as qubit
from ...groups import kernel


@kernel
def reset(qubits: ilist.IList[Qubit, Any]) -> None:
    """
    Reset qubits to the zero state.

    Args:
        qubits (IList[Qubit]): The qubits to reset.
    """
    qubit.reset(qubits)
