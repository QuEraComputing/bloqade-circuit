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
def _two_qubit_pauli_probability(
    probabilities: ilist.IList[tuple[str, float], Any], pauli: str
) -> float:
    probability = 0.0
    for pair in probabilities:
        current_probability = probability
        if pair[0] == pauli:
            current_probability = pair[1]
        probability = current_probability
    return probability


@kernel
def two_qubit_pauli_channel_shorthand(
    probabilities: ilist.IList[tuple[str, float], Any], control: Qubit, target: Qubit
) -> None:
    """
    A shorthand function for passing in a list of tuples of two-qubit Pauli products and corresponding
    probabilities, and randomly selects one of the Pauli products weighted by its probability.

    Example:
    two_qubit_pauli_channel_shorthand([("XX", 0.1), ("YI", 0.2), ("IZ": 0.3)], control, target)

    will apply "XX" with probability 0.1, "YI" with probability 0.2, "IZ" with probability 0.3. No error is applied with probability 0.4.

    Internally, this will just call two_qubit_pauli_channel.

    **NOTES**
    1. If a Pauli string is defined twice in the implementation, the last version will be used. For example, for [("XX", 0.1), ("XX", 0.3)], this would be the same as
    [("XX", 0.3)].
    2. The probabilities list can be of any length; we just convert the last N elements to a list of 15 probabilities.
    3. Strings that are not in `{IX, IY, IZ, XI, XX, XY, XZ, YI, YX, YY, YZ, ZI, ZX, ZY, ZZ}` are ignored.
    """
    two_qubit_pauli_channel(
        ilist.IList(
            [
                _two_qubit_pauli_probability(probabilities, "IX"),
                _two_qubit_pauli_probability(probabilities, "IY"),
                _two_qubit_pauli_probability(probabilities, "IZ"),
                _two_qubit_pauli_probability(probabilities, "XI"),
                _two_qubit_pauli_probability(probabilities, "XX"),
                _two_qubit_pauli_probability(probabilities, "XY"),
                _two_qubit_pauli_probability(probabilities, "XZ"),
                _two_qubit_pauli_probability(probabilities, "YI"),
                _two_qubit_pauli_probability(probabilities, "YX"),
                _two_qubit_pauli_probability(probabilities, "YY"),
                _two_qubit_pauli_probability(probabilities, "YZ"),
                _two_qubit_pauli_probability(probabilities, "ZI"),
                _two_qubit_pauli_probability(probabilities, "ZX"),
                _two_qubit_pauli_probability(probabilities, "ZY"),
                _two_qubit_pauli_probability(probabilities, "ZZ"),
            ]
        ),
        control,
        target,
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
