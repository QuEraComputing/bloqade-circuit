from typing import Any, Literal, TypeVar

from kirin.dialects import ilist

from bloqade.types import Qubit

from ...noise import _interface as noise
from ...groups import kernel


@kernel
def depolarize(p: float, qubits: ilist.IList[Qubit, Any]) -> None:
    """
    Apply a depolarizing noise channel to a list of qubits with probability `p`.

    For each qubit, this will randomly select one of the Pauli operators X, Y, Z
    with a probability `p / 3` and apply it to the qubit. No operator is applied
    with a probability of `1 - p`.

    Args:
        p (float): The probability with which a Pauli operator is applied.
        qubits (IList[Qubit, Any]): The list of qubits to which the noise channel is applied.
    """
    noise.depolarize(p, qubits)


N = TypeVar("N", bound=int)


@kernel
def depolarize2(
    p: float, controls: ilist.IList[Qubit, N], targets: ilist.IList[Qubit, N]
) -> None:
    """
    Symmetric two-qubit depolarization channel applied to a set of control and target qubits.

    For each pair of qubits from the `controls` and `targets` lists, this will randomly select one
    of the pauli products

    `{IX, IY, IZ, XI, XX, XY, XZ, YI, YX, YY, YZ, ZI, ZX, ZY, ZZ}`

    each with a probability `p / 15`. No noise is applied with a probability of `1 - p`.

    Args:
        p (float): The probability with which a Pauli product is applied.
        controls (IList[Qubit, N]): The list of control qubits.
        targets (IList[Qubit, N]): The list of target qubits.
    """
    noise.depolarize2(p, controls, targets)


@kernel
def single_qubit_pauli_channel(
    px: float, py: float, pz: float, qubits: ilist.IList[Qubit, Any]
) -> None:
    """
    Apply a Pauli error channel with weighted `px, py, pz`. No error is applied with a probability
    `1 - (px + py + pz)`.

    This randomly selects one of the three Pauli operators X, Y, Z, weighted with the given probabilities in that order.

    Args:
        probabilities (IList[float, Literal[3]]): A list of 3 probabilities corresponding to the probabilities `(p_x, p_y, p_z)` in that order.
        qubits (IList[Qubit, Any]): The list of qubits to which the noise channel is applied.
    """
    noise.single_qubit_pauli_channel(px, py, pz, qubits)


@kernel
def two_qubit_pauli_channel(
    probabilities: ilist.IList[float, Literal[15]],
    controls: ilist.IList[Qubit, N],
    targets: ilist.IList[Qubit, N],
) -> None:
    """
    Apply a Pauli product error with weighted `probabilities` to the set of control and target qubits.

    No error is applied with the probability `1 - sum(probabilities)`.

    For each pair of qubits from the `controls` and `targets` lists, this will randomly select one
    of the pauli products

    `{IX, IY, IZ, XI, XX, XY, XZ, YI, YX, YY, YZ, ZI, ZX, ZY, ZZ}`

    weighted with the corresponding list of probabilities.

    **NOTE**: The order of the given probabilities must match the order of the list of Pauli products above!
    """
    noise.two_qubit_pauli_channel(probabilities, controls, targets)


@kernel
def qubit_loss(p: float, qubits: ilist.IList[Qubit, Any]) -> None:
    """
    Apply a qubit loss channel to each of the qubits in the given list.

    Each qubit in the list is lost with a probability `p`.

    Args:
        p (float): Probability of the atom being lost.
        qubits (IList[Qubit, Any]): The list of qubits to which the noise channel is applied.
    """
    noise.qubit_loss(p, qubits)


@kernel
def correlated_qubit_loss(
    p: float, qubits: ilist.IList[ilist.IList[Qubit, Any], Any]
) -> None:
    """
    Apply correlated qubit loss channels to groups of qubits.

    For each group of qubits, applies a correlated loss channel where all qubits
    within the group are lost together with probability `p`. Loss events are independent
    between different groups.

    Args:
        p (float): Loss probability for each group.
        qubits (IList[IList[Qubit, Any], Any]): List of qubit groups. Each sublist
            represents a group of qubits to which a correlated loss channel is applied.

    Example:
        >>> q1 = squin.qubit.new(3) # First group: qubits 0, 1, 2
        >>> q2 = squin.qubit.new(3) # Second group: qubits 3, 4, 5
        >>> squin.broadcast.correlated_qubit_loss(0.5, [q1, q2])
        # Each group has 50% chance: either all qubits lost or none lost.
        # Group 1 and Group 2 outcomes are independent.
    """
    noise.correlated_qubit_loss(p, qubits)


# NOTE: actual stdlib that doesn't wrap statements starts here


@kernel
def bit_flip(p: float, qubits: ilist.IList[Qubit, Any]) -> None:
    """
    Apply a bit flip error channel to the qubits in the given list with probability `p`.

    Args:
        p (float): Probability of a bit flip error being applied.
        qubits (IList[Qubit, Any]): The list of qubits to which the noise channel is applied.
    """
    single_qubit_pauli_channel(p, 0, 0, qubits)
