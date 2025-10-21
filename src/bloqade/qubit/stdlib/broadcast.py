from typing import Any, TypeVar

from kirin.dialects import ilist

from bloqade.types import Qubit, MeasurementResult

from .. import _interface as _qubit
from .._prelude import kernel

N = TypeVar("N", bound=int)


@kernel
def reset(qubits: ilist.IList[Qubit, Any]) -> None:
    """
    Reset a list of qubits to the zero state.

    Args:
        qubits (IList[Qubit, Any]): The list of qubits to reset.
    """
    _qubit.reset(qubits)


@kernel
def measure(qubits: ilist.IList[Qubit, N]) -> ilist.IList[MeasurementResult, N]:
    """Measure a list of qubits.

    Args:
        qubits (IList[Qubit, N]): The list of qubits to measure.

    Returns:
        IList[MeasurementResult, N]: The list containing the results of the measurements.
            A MeasurementResult can represent both 0 and 1, but also atoms that are lost.
    """
    return _qubit.measure(qubits)
