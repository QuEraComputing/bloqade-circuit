from typing import Any

from kirin.dialects import ilist

from .. import _interface as qubit
from .._prelude import kernel


@kernel(typeinfer=True)
def new() -> qubit.Qubit:
    """Allocate a single new qubit

    Returns:
        (Qubit): The newly allocated qubit.
    """
    return qubit.new()


# NOTE: this is a special case, that doesn't use the usual simple / broadcast semantics.
@kernel(typeinfer=True)
def qalloc(n_qubits: int) -> ilist.IList[qubit.Qubit, Any]:
    """Allocate a new list of qubits.

    Args:
        n_qubits(int): The number of qubits to create.

    Returns:
        (ilist.IList[Qubit, n_qubits]) A list of qubits.
    """

    def _new(qid: int) -> qubit.Qubit:
        return qubit.new()

    return ilist.map(_new, ilist.range(n_qubits))
