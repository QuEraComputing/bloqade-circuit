"""Compile Bell pairs directly from Python to wire operations."""

from bloqade import squin
from bloqade.types import Qubit
from bloqade.squin.wire.lowering import wire_kernel


@wire_kernel
def bell(control: Qubit, target: Qubit) -> None:
    """Prepare a Bell pair on the caller's qubits."""
    squin.h(control)
    squin.cx(control, target)


@wire_kernel
def bell_pairs(n: int, flip: bool):
    """Prepare and measure `n` Bell pairs with an optional flip."""
    qs = squin.qalloc(2 * n)
    for i in range(n):
        control = qs[2 * i]
        bell(control, qs[2 * i + 1])
        if flip:
            squin.x(control)
    return squin.broadcast.measure(qs)


if __name__ == "__main__":
    bell_pairs.print()
