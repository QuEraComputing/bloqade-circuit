"""Turn registers of a constant size into separate wires.

`ExpandBroadcast` replaces a register operation with scalar operations when the
register types carry their lengths. A broadcast gate stays one statement. `UnpackRegister` then replaces
a local register with one `Alloc` per qubit, if every statement on the register's
linear chain reads a constant index. After both rules, 2 gates on one qubit are
neighbours on one wire, so a peephole rule can match them.

Both rules read static lengths from the types, so Kirin's type inference must run
first.
"""

import itertools
from typing import TypeAlias
from dataclasses import dataclass

from kirin import ir
from kirin.dialects import py, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.types import item_type
from bloqade.constants import constant_int
from bloqade.squin.wire import stmts
from bloqade.squin.wire.types import register_length
from bloqade.squin.rewrite.wire.driver import put


class ExpandBroadcast(RewriteRule):
    """Replace a register operation of static length with scalar operations.

    A `RegisterGate` or a `RegisterNoise` becomes one `Gate` or `Noise` on the
    groups of all positions, so the broadcast stays one parallel step. Position `k`
    forms the group of element `k` of every register. A `RegisterMeasure` or a
    `RegisterReset` becomes one scalar operation per position. Around the scalar
    operations, each element gets a `Borrow` and a `Release`. The classical results
    of the positions form one list per classical result, such as the bits of a
    `RegisterMeasure`.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Expand `node` if it is a register operation whose lengths are known."""
        if not isinstance(node, stmts.RegisterOperation):
            return RewriteResult()
        lengths = [register_length(register.type) for register in node.linear]
        if any(length is None for length in lengths):
            return RewriteResult()
        known = [length for length in lengths if length is not None]
        # A program that broadcasts over unequal lengths breaks a precondition.
        # The rule leaves that operation for the emitter's checks to report.
        if not node.truncates and len(set(known)) > 1:
            return RewriteResult()
        size = min(known, default=0)
        if isinstance(node, (stmts.RegisterGate, stmts.RegisterNoise)):
            steps = [range(size)] if size else []
        else:
            steps = [range(position, position + 1) for position in range(size)]
        registers = list(node.linear)
        collected: list[list[ir.SSAValue]] = [[] for _ in node.classical]
        for positions in steps:
            elements: list[tuple[int, ir.SSAValue]] = []
            wires: list[ir.SSAValue] = []
            for position in positions:
                index = py.Constant(position)
                index.insert_before(node)
                for k, register in enumerate(registers):
                    borrow = stmts.Borrow(register, index.result)
                    borrow.insert_before(node)
                    borrow.register_out.type = register.type
                    registers[k] = borrow.register_out
                    elements.append((k, index.result))
                    wires.append(borrow.wire)
            scalar = node.scalar(tuple(wires))
            scalar.insert_before(node)
            for (k, index), output in zip(elements, scalar.outputs, strict=True):
                release = stmts.Release(registers[k], index, output)
                release.insert_before(node)
                release.register_out.type = registers[k].type
                registers[k] = release.register_out
            for items, value in zip(collected, scalar.classical, strict=True):
                items.append(value)
        for result, items in zip(node.classical, collected, strict=True):
            made = ilist.New(tuple(items), elem_type=item_type(result.type))
            made.insert_before(node)
            result.replace_by(made.result)
        for output, register in zip(node.outputs, registers, strict=True):
            output.replace_by(register)
        node.delete()
        return RewriteResult(has_done_something=True)


@dataclass(frozen=True)
class View:
    """Name the range of the root register that one register value holds.

    The root register has the view `View(0, 0, size)`. A `TakeSlice` creates a view
    with a new `key` for its range.
    """

    key: int
    offset: int
    """The position of the first element of the range in the root register."""
    size: int


@dataclass(frozen=True)
class BorrowStep:
    """Record a `Borrow` of the root `position`."""

    stmt: stmts.Borrow
    position: int


@dataclass(frozen=True)
class ReleaseStep:
    """Record a `Release` into the root `position`."""

    stmt: stmts.Release
    position: int


@dataclass(frozen=True)
class LengthStep:
    """Record a `Length` of a view that holds `size` positions."""

    stmt: stmts.Length
    size: int


@dataclass(frozen=True)
class MoveStep:
    """Record a `TakeSlice` or a `PutSlice`, which moves positions between views."""

    stmt: stmts.TakeSlice | stmts.PutSlice


@dataclass(frozen=True)
class FreeStep:
    """Record the free of the root register."""

    stmt: stmts.FreeRegister | stmts.DiscardRegister


Step: TypeAlias = BorrowStep | ReleaseStep | LengthStep | MoveStep | FreeStep
"""Record one statement that uses a register of the root, and what it reads."""


class UnpackRegister(RewriteRule):
    """Replace a local register of constant size with one wire per qubit.

    The rule starts at an `AllocRegister` with a constant size or at a
    `PackRegister`, which is the root register. `plan` lists every statement that
    uses the root or a slice of it. Each one must be a `Borrow` or `Release` at a
    constant index, a `Length`, a `TakeSlice` or `PutSlice` with constant bounds, or
    the final free, all in the block of the root. If any statement breaks these
    rules, the rule leaves the register unchanged. A loop, a branch or a call that
    takes the register breaks them.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Unpack the register that `node` creates, if every use is static."""
        if isinstance(node, stmts.AllocRegister):
            size = constant_int(node.size)
        elif isinstance(node, stmts.PackRegister):
            size = len(node.wires)
        else:
            return RewriteResult()
        if size is None or (steps := plan(node, size)) is None:
            return RewriteResult()
        if isinstance(node, stmts.PackRegister):
            slots: list[ir.SSAValue] = list(node.wires)
        else:
            slots = []
            for _ in range(size):
                alloc = stmts.Alloc()
                alloc.insert_before(node)
                slots.append(alloc.result)
        for step in steps:
            match step:
                case BorrowStep(stmt, position):
                    stmt.wire.replace_by(slots[position])
                case ReleaseStep(stmt, position):
                    slots[position] = stmt.wire
                case LengthStep(stmt, count):
                    stmt.result.replace_by(put(py.Constant(count), stmt).result)
                case FreeStep(stmt):
                    for wire in slots:
                        put(stmts.Free(wire), stmt)
                case MoveStep():
                    # The slots follow the qubits through the move, so the move
                    # needs no replacement.
                    pass
        # Each register value has one use, and that use comes later in the block.
        # Deleting from the end keeps every deleted result unused.
        for step in reversed(steps):
            step.stmt.delete()
        node.delete()
        return RewriteResult(has_done_something=True)


def plan(node: ir.Statement, size: int) -> list[Step] | None:
    """Return the statements that use the register of `node` or its slices, or None.

    The function reads the block of `node` in order and tracks the view of each
    register value. A position belongs to one view at a time, and it is full or
    borrowed. A `Borrow` needs a full position of its view, and a `Release` needs a
    borrowed one. A `TakeSlice` moves full positions to a new view, and a `PutSlice`
    moves them back. The list ends with the free of the root, which needs every
    position back in the root and full. The function returns None if a statement
    breaks the rules of `UnpackRegister`.
    """
    block = node.parent_block
    root = View(0, 0, size)
    owner = [root.key] * size
    full = [True] * size
    views: dict[ir.SSAValue, View] = {}
    steps: list[Step] = []
    keys = itertools.count(root.key + 1)

    def track(value: ir.SSAValue, view: View) -> bool:
        """Track `value` if its one use sits in the block of the root."""
        uses = list(value.uses)
        if len(uses) != 1 or uses[0].stmt.parent_block is not block:
            return False
        views[value] = view
        return True

    def position(view: View, index: ir.SSAValue) -> int | None:
        """Return the root position of the constant `index` into `view`, or None."""
        at = constant_int(index)
        if at is None or not 0 <= at < view.size:
            return None
        return view.offset + at

    def holds(view: View, start: int, count: int) -> bool:
        """Check that `view` owns the full positions from `start` on."""
        span = range(start, start + count)
        return all(owner[p] == view.key and full[p] for p in span)

    if not track(node.results[0], root):
        return None
    stmt = node.next_stmt
    while stmt is not None:
        if not any(value in views for value in stmt.args):
            stmt = stmt.next_stmt
            continue
        if isinstance(stmt, (stmts.Borrow, stmts.Release)):
            view = views.pop(stmt.register)
            at = position(view, stmt.index)
            borrow = isinstance(stmt, stmts.Borrow)
            # A `Borrow` empties a full position, and a `Release` fills it again.
            if at is None or owner[at] != view.key or full[at] != borrow:
                return None
            full[at] = not borrow
            steps.append(
                BorrowStep(stmt, at)
                if isinstance(stmt, stmts.Borrow)
                else ReleaseStep(stmt, at)
            )
            if not track(stmt.register_out, view):
                return None
        elif isinstance(stmt, stmts.Length):
            view = views.pop(stmt.register)
            steps.append(LengthStep(stmt, view.size))
            if not track(stmt.register_out, view):
                return None
        elif isinstance(stmt, stmts.TakeSlice):
            view = views.pop(stmt.register)
            start, count = constant_int(stmt.start), constant_int(stmt.length)
            if start is None or count is None or start < 0 or start + count > view.size:
                return None
            part = View(next(keys), view.offset + start, count)
            if not holds(view, part.offset, count):
                return None
            for p in range(part.offset, part.offset + count):
                owner[p] = part.key
            steps.append(MoveStep(stmt))
            if not track(stmt.register_out, view) or not track(
                stmt.slice_register, part
            ):
                return None
        elif isinstance(stmt, stmts.PutSlice):
            view = views.pop(stmt.register)
            part = views.pop(stmt.slice_register, None)
            start = constant_int(stmt.start)
            if part is None or start is None or part.offset != view.offset + start:
                return None
            if not holds(part, part.offset, part.size):
                return None
            for p in range(part.offset, part.offset + part.size):
                owner[p] = view.key
            steps.append(MoveStep(stmt))
            if not track(stmt.register_out, view):
                return None
        elif isinstance(stmt, (stmts.FreeRegister, stmts.DiscardRegister)):
            view = views.pop(stmt.register)
            if view != root or views or not holds(root, 0, size):
                return None
            steps.append(FreeStep(stmt))
            return steps
        else:
            return None
        stmt = stmt.next_stmt
    return None
