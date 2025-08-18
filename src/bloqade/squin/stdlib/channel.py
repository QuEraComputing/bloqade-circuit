from bloqade.types import Qubit
from bloqade.squin.op.types import PauliOp

from .. import noise, qubit as _qubit, kernel


@kernel
def pauli_error(basis: PauliOp, p: float, qubit: Qubit) -> None:
    """Apply the pauli operator given as basis with a probability p to qubit.

    NOTE: the `PauliError` actually supports multiple qubits and multi-site bases,
    it's only the short-hand definition here that is limited to a single qubit.
    If you want to define a pauli error for multiple qubits, you can do so using
    the statement, for example

    ```python
    q = squin.qubit.new(3)
    multi_qubit_pauli = squin.op.pauli_string(string="XYZ")
    pauli_error = squin.noise.pauli_error(basis=multi_qubit_pauli, p=0.1)
    squin.qubit.apply(pauli_error, q[0], q[1], q[2])
    ```

    """
    op = noise.pauli_error(basis, p)
    _qubit.apply(op, qubit)


@kernel
def depolarize(p: float, qubit: Qubit) -> None:
    """Apply depolarization error with probability p to qubit.

    This means, that with a probability p/3 one of the three Pauli operators is applied.
    Which Pauli operator is applied is chosen at random with equal probability.
    """
    op = noise.depolarize(p)
    _qubit.apply(op, qubit)


@kernel
def depolarize2(p: float, qubit1: Qubit, qubit2: Qubit) -> None:
    """Apply the correlated two-qubit depolarization error with probability p to qubits.

    This means, that with a probability of p/15 one of the Pauli products {XX, XY, XZ, XI, YX, YY, ...}
    is applied to the qubit pair. Which Pauli product is applied is chosen at random with equal probability.
    """

    op = noise.depolarize2(p)
    _qubit.apply(op, qubit1, qubit2)


@kernel
def single_qubit_pauli_channel(params: list[float], qubit: Qubit) -> None:
    """Apply the single qubit Pauli error with probabilities px, py, pz, respectively, to the qubit.

    Similar to `depolarize`, but with distinct probabilities. An error occurs with the probability `px + py + pz`.
    Which operator is applied is chosen at random, but weighed with the respective probabilities.
    """
    op = noise.single_qubit_pauli_channel(params)
    _qubit.apply(op, qubit)


@kernel
def two_qubit_pauli_channel(params: list[float], qubit1: Qubit, qubit2: Qubit) -> None:
    """Apply the two-qubit correlated Pauli error with probabilities given in the list above.

    This means one of the operator products

    {IX, IY, IZ, XI, XX, XY, XZ, YI, YX, YY, YZ, ZI, ZX, ZY, ZZ}

    is applied. The choice of which is weighed by the given probabilities.

    NOTE: the given parameters are ordered as given in the list above!

    """
    op = noise.two_qubit_pauli_channel(params)
    _qubit.apply(op, qubit1, qubit2)


@kernel
def qubit_loss(p: float, qubit: Qubit) -> None:
    """Apply a qubit loss channel with probability p.

    When a loss channel is applied, the qubit is marked as lost by setting its state accordingly.
    """
    op = noise.qubit_loss(p)
    _qubit.apply(op, qubit)
