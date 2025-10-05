from kirin.dialects import ilist

from bloqade.types import Qubit

from .. import broadcast
from ...groups import kernel


@kernel
def reset(qubit: Qubit) -> None:
    """
    Reset qubits to the zero state.

    Args:
        qubit (Qubit): The qubit to reset.
    """
    broadcast.reset(ilist.IList([qubit]))
