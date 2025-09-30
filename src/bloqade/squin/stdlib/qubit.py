from kirin.dialects import ilist

from .. import kernel
from ..qubit import new_qubit


@kernel
def new(n_qubits: int):
    """Create a new list of qubits.

    Args:
        n_qubits(int): The number of qubits to create.

    Returns:
        (ilist.IList[Qubit, n_qubits]) A list of qubits.
    """

    def _new(qid: int):
        return new_qubit()

    return ilist.map(_new, ilist.range(n_qubits))
