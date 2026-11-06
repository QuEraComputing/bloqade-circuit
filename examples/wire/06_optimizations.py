"""Join borrows, unpack a fixed register and merge consecutive rotations."""

from bloqade import squin, native
from bloqade.squin.passes.wire_unpack import JoinBorrows, UnpackRegisters
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_rotations import MergeNativeRotations


@native.kernel
def rotations():
    """Apply rotations in radians to two qubits."""
    qs = squin.qalloc(2)
    native.rx(0.2, qs[0])
    native.rx(0.3, qs[0])
    native.ry(0.1, qs[1])


if __name__ == "__main__":
    wired = SquinToWire().emit(rotations)
    wired.print()
    JoinBorrows(wired.dialects)(wired)
    wired.print()
    UnpackRegisters(wired.dialects)(wired)
    wired.print()
    MergeNativeRotations(wired.dialects)(wired)
    wired.print()
