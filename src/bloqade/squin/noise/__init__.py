from . import stmts as stmts
from ._dialect import dialect as dialect
from ._wrapper import (
    depolarize as depolarize,
    qubit_loss as qubit_loss,
    depolarize2 as depolarize2,
    pauli_error as pauli_error,
    two_qubit_pauli_channel as two_qubit_pauli_channel,
    single_qubit_pauli_channel as single_qubit_pauli_channel,
)
