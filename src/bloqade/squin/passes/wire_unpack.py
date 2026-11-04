"""Turn the registers of a wire method into wires where the indices allow it."""

from dataclasses import dataclass

from kirin import ir
from kirin.passes import Pass
from kirin.rewrite import Walk, Chain, Fixpoint, DeadCodeElimination
from kirin.rewrite.abc import RewriteResult

from bloqade.squin.rewrite.wire.join import JoinBorrow, HoistBorrow
from bloqade.squin.rewrite.wire.unpack import UnpackRegister, ExpandBroadcast


@dataclass
class JoinBorrows(Pass):
    """Join each `Release` with a later `Borrow` of the same register element.

    The pass first moves each `Borrow` above the `Release` statements of other
    constant elements. It works on registers of any size, including parameters.
    """

    name = "join_borrows"

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        """Run the hoisting and joining rules until neither changes the method."""
        rules = Walk(Chain(JoinBorrow(), HoistBorrow()))
        return Fixpoint(rules).rewrite(mt.code)


@dataclass
class UnpackRegisters(Pass):
    """Expand static broadcasts, join borrows, then unpack constant-size registers.

    The pass works on one method and leaves its callees alone. A register that a
    loop, a branch or a call takes stays a register, but its static broadcasts
    still become scalar operations, and its borrows still join.
    """

    name = "unpack_registers"

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        """Run the expansion, the joining, the unpacking and dead-code removal."""
        result = Walk(ExpandBroadcast()).rewrite(mt.code)
        result = JoinBorrows(self.dialects).unsafe_run(mt).join(result)
        result = Walk(UnpackRegister()).rewrite(mt.code).join(result)
        dead = Fixpoint(Walk(DeadCodeElimination())).rewrite(mt.code)
        return dead.join(result)
