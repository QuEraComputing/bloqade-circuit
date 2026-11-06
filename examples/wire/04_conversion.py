"""Convert a kernel with a function call, a loop and a branch."""

from bloqade import squin
from bloqade.types import Qubit
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin


@squin.kernel
def entangle(control: Qubit, target: Qubit):
    """Apply a Hadamard gate and a controlled X gate."""
    squin.h(control)
    squin.cx(control, target)


@squin.kernel
def circuit(rounds: int, flip_second: bool):
    """Repeat an entangling operation and optionally flip the second measurement outcome."""
    qs = squin.qalloc(2)
    for _ in range(rounds):
        entangle(qs[0], qs[1])
    if flip_second:
        squin.x(qs[1])
    return squin.broadcast.measure(qs)


if __name__ == "__main__":
    wired = SquinToWire().emit(circuit)
    wired.print()
    restored = WireToSquin().emit(wired)
    restored.print()
