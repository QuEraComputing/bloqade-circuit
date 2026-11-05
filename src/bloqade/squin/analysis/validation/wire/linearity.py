"""Check that each wire and register has exactly one use.

The use must sit in the region that defines the value. A branch may use an outer wire
once, and a loop body must take every wire as a block argument.
"""

from dataclasses import dataclass
from collections.abc import Iterable

from kirin import ir, types, interp
from kirin.lattice import EmptyLattice
from kirin.dialects import py, scf, func
from kirin.validation import ValidationPass
from kirin.analysis.forward import ForwardFrame

from bloqade.constants import constant_int
from bloqade.squin.wire.group import WIRE_DIALECTS
from bloqade.squin.wire.types import linear_paths
from bloqade.squin.wire.traits import Threads, ReferenceForm

from .calls import WireCheck, yield_top

KEY: str = "squin.wire.linearity"
"""Name the registry key of the method tables of `LinearityCheck`."""

QUANTUM_CONSUMERS: tuple[type[ir.Statement], ...] = (
    py.tuple.New,
    func.Invoke,
    func.Return,
    scf.For,
    scf.Yield,
)
"""Name the statements outside the wire dialect that can take a quantum operand."""


def _anchor(stmt: ir.Statement, region: ir.Region) -> ir.Statement | None:
    """Return the statement of `region` that holds `stmt`, or None if none holds it."""
    node: ir.Statement | None = stmt
    while node is not None and node.parent_region is not region:
        node = node.parent_stmt
    return node


def misuse(users: list[ir.Statement], region: ir.Region) -> str | None:
    """Return why the statements `users` break the use rule in `region`, or None.

    `users` holds one entry for each use of a linear value that `region` defines.
    The rule allows one use by a statement of `region`. It also allows uses inside an
    `scf.IfElse` of `region` if each branch keeps the rule on its own.
    """
    if not users:
        return "has no use"
    groups: dict[ir.Statement, list[ir.Statement]] = {}
    for user in users:
        anchor = _anchor(user, region)
        if anchor is None:
            return "has a use outside the region that defines it"
        groups.setdefault(anchor, []).append(user)
    for anchor, inside in groups.items():
        nested = any(user is not anchor for user in inside)
        if nested and not isinstance(anchor, scf.IfElse):
            return (
                f"crosses into the body of '{anchor.name}' outside its block arguments"
            )
    if len(groups) > 1:
        return f"has {len(users)} uses"
    ((anchor, inside),) = groups.items()
    if inside == [anchor]:
        return None
    if anchor in inside:
        return f"has {len(users)} uses"
    # The loop above returns for every nested use outside a branch.
    assert isinstance(anchor, scf.IfElse)
    for body in (anchor.then_body, anchor.else_body):
        branch = [user for user in inside if _anchor(user, body) is not None]
        if (reason := misuse(branch, body)) is not None:
            return f"{reason} in a branch"
    return None


def _region_of(value: ir.SSAValue) -> ir.Region | None:
    """Return the region that defines `value`."""
    if isinstance(value, ir.BlockArgument):
        return value.owner.parent
    owner = value.owner
    return owner.parent_region if isinstance(owner, ir.Statement) else None


@dataclass
class LinearityCheck(WireCheck):
    """Record a validation error for each linear value that breaks the use rule."""

    keys = (KEY, "absint")

    def check_uses(self, values: Iterable[ir.SSAValue], node: ir.IRNode) -> None:
        """Check one consuming use per quantum tuple field along each execution path."""
        for value in values:
            try:
                paths = linear_paths(value.type)
            except ValueError:
                # `BoundaryCheck` reports a quantum field without a fixed tuple path.
                continue
            region = _region_of(value)
            if region is None:
                continue
            for path in paths:
                users = self.field_users(value, path)
                if (reason := misuse(users, region)) is not None:
                    suffix = "" if not path else f" at tuple field {path}"
                    self.error(
                        node,
                        f"The linear value '{value.name or repr(value)}'{suffix}"
                        f" {reason}.",
                    )

    def field_users(
        self, value: ir.SSAValue, path: tuple[int, ...]
    ) -> list[ir.Statement]:
        """Return the statements that use the quantum field at `path` of `value`.

        An empty path names `value` itself. The check records an error for each use that
        cannot consume a quantum value. A wire statement of another dialect can consume
        one, and its `ReferenceForm` trait marks it.
        """
        users: list[ir.Statement] = []
        for use in value.uses:
            user = use.stmt
            if path and isinstance(user, py.GetItem) and use.index == 0:
                if self.tuple_field(user, value) != path[0]:
                    continue
            elif not (
                user.dialect in WIRE_DIALECTS
                or user.has_trait(ReferenceForm)
                or isinstance(user, QUANTUM_CONSUMERS)
            ):
                hint = (
                    " A wire statement of another dialect needs a ReferenceForm trait."
                    if user.has_trait(Threads)
                    else ""
                )
                self.error(user, f"'{user.name}' cannot consume a quantum value.{hint}")
            users.append(user)
        return users

    def tuple_field(self, user: py.GetItem, value: ir.SSAValue) -> int | None:
        """Return the field of the tuple `value` that `user` reads, or None.

        `BoundaryCheck` reports a runtime index and an index outside the tuple
        bounds.
        """
        index = constant_int(user.index)
        assert isinstance(value.type, types.Generic)
        size = len(value.type.vars)
        if index is None or not -size <= index < size:
            return None
        return index % size

    def frame_eval(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement
    ) -> interp.StatementResult[EmptyLattice]:
        """Check the uses of the results of `node`, then run its rule."""
        self.check_uses(node.results, node)
        return super().frame_eval(frame, node)

    def frame_call(
        self,
        frame: ForwardFrame[EmptyLattice],
        node: ir.Statement,
        *args: EmptyLattice,
        **kwargs: EmptyLattice,
    ) -> EmptyLattice:
        """Check the uses of the parameters of the function `node`, then run its body."""
        trait = node.get_trait(ir.CallableStmtInterface)
        if trait is not None:
            self.check_uses(trait.get_callable_region(node).blocks[0].args[1:], node)
        return super().frame_call(frame, node, *args, **kwargs)


@func.dialect.register(key=KEY)
class Functions(interp.MethodTable):
    """Check each callee once."""

    @interp.impl(func.Invoke)
    def invoke(
        self,
        check: LinearityCheck,
        frame: ForwardFrame[EmptyLattice],
        stmt: func.Invoke,
    ) -> tuple[EmptyLattice, ...]:
        """Check the uses inside the callee."""
        return check.run_callee(stmt)


@scf.dialect.register(key=KEY)
class ControlFlow(interp.MethodTable):
    """Check the uses of the block arguments of loops and branches."""

    @interp.impl(scf.For)
    @interp.impl(scf.IfElse)
    def structured(
        self,
        check: LinearityCheck,
        frame: ForwardFrame[EmptyLattice],
        stmt: ir.Statement,
    ) -> tuple[EmptyLattice, ...]:
        """Check the uses of each block argument, then run each body once."""
        return check.run_regions(stmt, lambda block: check.check_uses(block.args, stmt))

    @interp.impl(scf.Yield)
    def yield_(
        self, check: LinearityCheck, frame: ForwardFrame[EmptyLattice], stmt: scf.Yield
    ) -> interp.YieldValue[EmptyLattice]:
        """Return the top element for each yielded value."""
        return yield_top(stmt)


class LinearityValidation(ValidationPass[ForwardFrame[EmptyLattice]]):
    """Check that a wire squin method uses each wire and register exactly once."""

    def name(self) -> str:
        """Return the pass name that validation reports show."""
        return "squin wire linearity"

    def run(
        self, method: ir.Method
    ) -> tuple[ForwardFrame[EmptyLattice], list[ir.ValidationError]]:
        """Run `LinearityCheck` and return its frame and errors."""
        analysis = LinearityCheck(method.dialects)
        frame, _ = analysis.run(method)
        return frame, analysis.get_validation_errors()
