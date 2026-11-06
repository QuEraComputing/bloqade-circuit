"""Compile Bell pairs directly from Python to wire operations."""

from bloqade import squin
from bloqade.squin.wire.lowering import wire_kernel


@wire_kernel
def bell_pairs(n: int):
    """Prepare and measure `n` Bell pairs."""
    qs = squin.qalloc(2 * n)
    for i in range(n):
        squin.h(qs[2 * i])
        squin.cx(qs[2 * i], qs[2 * i + 1])
    return squin.broadcast.measure(qs)


if __name__ == "__main__":
    bell_pairs.print()
