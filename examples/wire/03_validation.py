"""Validate qubit use and register access in an entangled state preparation."""

from bloqade import squin
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.analysis.validation.wire import WireValidation


@squin.kernel
def ghz_state():
    """Entangle three qubits so that measurement gives either 000 or 111."""
    qs = squin.qalloc(3)
    squin.h(qs[0])
    squin.cx(qs[0], qs[1])
    squin.cx(qs[1], qs[2])
    return squin.broadcast.measure(qs)


if __name__ == "__main__":
    wired = SquinToWire().emit(ghz_state)
    WireValidation().check(wired)
    wired.print()
