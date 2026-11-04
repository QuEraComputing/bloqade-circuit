"""Join a `Release` and a later `Borrow` of the same register element.

The emitter wraps each gate on a register element in a `Borrow` and a `Release`. So
`h(qs[0]); h(qs[0])` gives `Borrow`, gate, `Release`, `Borrow`, gate, `Release`, and
the 2 gates are no neighbours on one wire. `JoinBorrow` removes a `Release` whose next
statement on the register borrows the same element again. `HoistBorrow` moves a
`Borrow` above a `Release` of another constant element, so that more pairs meet.
Both rules work on registers that `UnpackRegister` cannot remove, such as function
parameters and registers in loops.
"""

from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.constants import constant_int
from bloqade.squin.wire import stmts


def released(node: ir.Statement) -> stmts.Release | None:
    """Return the `Release` whose register result `node` borrows from, or None.

    The `Borrow` `node` must be the only use of that result and sit in its block.
    """
    if not isinstance(node, stmts.Borrow):
        return None
    release = node.register.owner
    if not isinstance(release, stmts.Release) or len(release.register_out.uses) != 1:
        return None
    if release.parent_block is not node.parent_block:
        return None
    return release


def same_index(left: ir.SSAValue, right: ir.SSAValue) -> bool:
    """Check whether 2 indices are one value or equal constants."""
    if left is right:
        return True
    a, b = constant_int(left), constant_int(right)
    return a is not None and a == b


def distinct_index(left: ir.SSAValue, right: ir.SSAValue) -> bool:
    """Check whether 2 indices are different constants."""
    a, b = constant_int(left), constant_int(right)
    return a is not None and b is not None and a != b


class JoinBorrow(RewriteRule):
    """Replace `Release(r, i, w)` and a later `Borrow` at `i` with the wire `w`.

    Before the `Release` and after the `Borrow`, the register lends element `i` to
    a wire. So the rule reads the register after the `Borrow` as the register
    before the `Release`.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Join `node` with the `Release` before it, if both read the same element."""
        release = released(node)
        if release is None or not isinstance(node, stmts.Borrow):
            return RewriteResult()
        if not same_index(release.index, node.index):
            return RewriteResult()
        node.wire.replace_by(release.wire)
        node.register_out.replace_by(release.register)
        node.delete()
        release.delete()
        return RewriteResult(has_done_something=True)


class HoistBorrow(RewriteRule):
    """Move a `Borrow` at `j` above the `Release` at `i` before it, if `i != j`.

    The 2 statements read different elements, so their order makes no difference.
    The rule only moves a `Borrow` earlier, so a fixpoint of it ends.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Swap `node` with the `Release` before it, if they read different elements."""
        release = released(node)
        if release is None or not isinstance(node, stmts.Borrow):
            return RewriteResult()
        if not distinct_index(release.index, node.index):
            return RewriteResult()
        # The emitter puts each index constant just before its `Borrow`. The
        # constant has no operands, so the rule moves it above the `Release`.
        index = node.index.owner
        between = release.next_stmt
        while between is not None and between is not node:
            if between is index:
                between.detach()
                between.insert_before(release)
                break
            between = between.next_stmt
        borrow = stmts.Borrow(release.register, node.index)
        borrow.insert_before(release)
        borrow.register_out.type = release.register.type
        moved = stmts.Release(borrow.register_out, release.index, release.wire)
        moved.insert_before(release)
        moved.register_out.type = release.register.type
        node.wire.replace_by(borrow.wire)
        node.register_out.replace_by(moved.register_out)
        node.delete()
        release.delete()
        return RewriteResult(has_done_something=True)
