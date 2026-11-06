"""Write a Bell circuit to a Jeff file and reconstruct it."""

from pathlib import Path
from tempfile import TemporaryDirectory

from bloqade import squin
from bloqade.jeff import JeffToWire, WireToJeff, emit_jeff, load_jeff
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin


@squin.kernel
def bell_pair():
    """Prepare a Bell pair and measure both qubits."""
    qs = squin.qalloc(2)
    squin.h(qs[0])
    squin.cx(qs[0], qs[1])
    return squin.broadcast.measure(qs)


if __name__ == "__main__":
    wired = SquinToWire().emit(bell_pair)
    jeff = WireToJeff().emit(wired)
    jeff.print()
    with TemporaryDirectory() as directory:
        path = str(Path(directory) / "bell.jeff")
        emit_jeff(jeff).write_out(path)
        imported = JeffToWire().emit(load_jeff(path))
    restored = WireToSquin().emit(imported)
