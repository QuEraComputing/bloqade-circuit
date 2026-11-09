"""Merge the runs of native single-qubit rotations of a kernel.

Nothing runs this simplification by default. A caller opts in with
`merge_native_rotations`, or with the pass `MergeNativeRotations` on a wire method.
"""

from dataclasses import dataclass

from kirin import ir
from kirin.passes import Pass, HintConst
from kirin.rewrite import Walk, Fixpoint, ConstantFold, DeadCodeElimination
from kirin.rewrite.abc import RewriteResult
from kirin.ir.exception import ValidationErrorGroup

from bloqade.squin.passes.wire_unpack import JoinBorrows
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin
from bloqade.squin.rewrite.wire.rotations import MergeRotations


@dataclass
class MergeNativeRotations(Pass):
    """Fold constants, join borrows, then merge each run of native rotations.

    Constant folding turns angles such as `pi / 2 / (2 * pi)` into constants, which
    the merge needs. The pass folds constants only, and leaves every other
    statement as it is. Joining borrows puts 2 gates on one register element next to
    each other on one wire. The pass works on one wire method and leaves its callees
    alone.
    """

    name = "merge_native_rotations"

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        """Run the folding, the joining, the merge and dead-code removal."""
        result = HintConst(self.dialects).unsafe_run(mt)
        folded = Fixpoint(Walk(ConstantFold())).rewrite(mt.code)
        result = folded.join(result)
        result = JoinBorrows(self.dialects).unsafe_run(mt).join(result)
        result = Fixpoint(Walk(MergeRotations())).rewrite(mt.code).join(result)
        dead = Fixpoint(Walk(DeadCodeElimination())).rewrite(mt.code)
        return dead.join(result)


def merge_native_rotations(
    kernel: ir.Method,
    wire_dialects: tuple[ir.Dialect, ...] = (),
    *,
    no_raise: bool = False,
) -> ir.Method:
    """Return a copy of `kernel` in which `MergeNativeRotations` merges each run.

    The function converts `kernel` and its callees to wire squin, runs
    `MergeNativeRotations` on each wire method, and converts the result back. The
    copy acts on every qubit like `kernel`, up to a global phase. `kernel` stays
    unchanged. `wire_dialects` holds the dialects of the wire statements that other
    dialects of `kernel` emit, such as Gemini.

    If `kernel` has no wire form and `no_raise` is True, the function returns
    `kernel` itself. Otherwise it raises the conversion error.
    """
    try:
        converter = SquinToWire(wire_dialects)
        wired = converter.emit(kernel)
        for method in converter.converted.values():
            MergeNativeRotations(method.dialects)(method)
        return WireToSquin(wire_dialects).emit(wired)
    except (ir.ValidationError, ValidationErrorGroup):
        if no_raise:
            return kernel
        raise
