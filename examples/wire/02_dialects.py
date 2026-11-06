"""Show state, gate and noise operations in a converted kernel."""

from bloqade import squin
from bloqade.squin.passes.squin_to_wire import SquinToWire


@squin.kernel
def noisy_bell_pair(probability: float, n: int):
    """Prepare a Bell pair and apply depolarizing noise to its first qubit."""
    qs = squin.qalloc(n_qubits=n)
    squin.h(qs[0])
    squin.cx(qs[0], qs[1])
    squin.depolarize(probability, qs[0])
    return squin.broadcast.measure(qs)


if __name__ == "__main__":
    wired = SquinToWire().emit(noisy_bell_pair)
    wired.print()
