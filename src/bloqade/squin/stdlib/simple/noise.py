from typing import Any, Literal, TypeVar

from kirin.dialects import ilist

from bloqade.types import Qubit

from .. import broadcast
from ...groups import kernel


@kernel
def depolarize(p: float, qubit: Qubit) -> None:
    """
    Apply a depolarizing noise channel to a qubit with probability `p`.

    This will randomly select one of the Pauli operators X, Y, Z
    with a probability `p / 3` and apply it to the qubit. No operator is applied
    with a probability of `1 - p`.

    Args:
        p (float): The probability with which a Pauli operator is applied.
        qubit (Qubit): The qubit to which the noise channel is applied.
    """
    broadcast.depolarize(p, ilist.IList([qubit]))


N = TypeVar("N", bound=int)


@kernel
def depolarize2(p: float, control: Qubit, target: Qubit) -> None:
    """
    Symmetric two-qubit depolarization channel applied to a pair of qubits.

    This will randomly select one of the pauli products

    `{IX, IY, IZ, XI, XX, XY, XZ, YI, YX, YY, YZ, ZI, ZX, ZY, ZZ}`

    each with a probability `p / 15`. No noise is applied with a probability of `1 - p`.

    Args:
        p (float): The probability with which a Pauli product is applied.
        control (Qubit): The control qubit.
        target (Qubit): The target qubit.
    """
    broadcast.depolarize2(p, ilist.IList([control]), ilist.IList([target]))


@kernel
def single_qubit_pauli_channel(px: float, py: float, pz: float, qubit: Qubit) -> None:
    """
    Apply a Pauli error channel with weighted `px, py, pz`. No error is applied with a probability
    `1 - (px + py + pz)`.

    This randomly selects one of the three Pauli operators X, Y, Z, weighted with the given probabilities in that order.

    Args:
        probabilities (IList[float, Literal[3]]): A list of 3 probabilities corresponding to the probabilities `(p_x, p_y, p_z)` in that order.
        qubit (Qubit): The qubit to which the noise channel is applied.
    """
    broadcast.single_qubit_pauli_channel(px, py, pz, ilist.IList([qubit]))


@kernel
def two_qubit_pauli_channel(
    probabilities: ilist.IList[float, Literal[15]], control: Qubit, target: Qubit
) -> None:
    """
    Apply a Pauli product error with weighted `probabilities` to the pair of qubits.

    No error is applied with the probability `1 - sum(probabilities)`.

    This will randomly select one of the pauli products

    `{IX, IY, IZ, XI, XX, XY, XZ, YI, YX, YY, YZ, ZI, ZX, ZY, ZZ}`

    weighted with the corresponding list of probabilities.

    **NOTE**: The order of the given probabilities must match the order of the list of Pauli products above!
    """
    broadcast.two_qubit_pauli_channel(
        probabilities, ilist.IList([control]), ilist.IList([target])
    )


@kernel
def qubit_loss(p: float, qubit: Qubit) -> None:
    """
    Apply a qubit loss channel to the given qubit.

    The qubit is lost with a probability `p`.

    Args:
        p (float): Probability of the atom being lost.
        qubit (Qubit): The qubit to which the noise channel is applied.
    """
    broadcast.qubit_loss(p, ilist.IList([qubit]))


@kernel
def correlated_qubit_loss(p: float, qubits: ilist.IList[Qubit, Any]) -> None:
    """
    Apply a correlated qubit loss channel to the given qubits.

    All qubits are lost together with a probability `p`.

    Args:
        p (float): Probability of the qubits being lost.
        qubits (IList[Qubit, Any]): The list of qubits to which the correlated noise channel is applied.
    """
    broadcast.correlated_qubit_loss(p, ilist.IList([qubits]))


# NOTE: actual stdlib that doesn't wrap statements starts here


@kernel
def bit_flip(p: float, qubit: Qubit) -> None:
    """
    Apply a bit flip error channel to the qubit with probability `p`.

    Args:
        p (float): Probability of a bit flip error being applied.
        qubit (Qubit): The qubit to which the noise channel is applied.
    """
    single_qubit_pauli_channel(p, 0, 0, qubit)
