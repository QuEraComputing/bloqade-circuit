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
from kirin.ir.exception import ValidationErrorGroup
from kirin.analysis.forward import ForwardFrame

from bloqade.types import is_subtype
from bloqade.constants import constant_int
from bloqade.squin.wire import stmts
from bloqade.squin.wire.types import (
    is_linear,
    linear_paths,
    contains_linear,
)
from bloqade.squin.wire.traits import Threads, ReferenceForm
from bloqade.squin.analysis.validation.wire.calls import CachedCalls

KEY = "squin.wire.linearity"
"""Name the registry key of the method tables of `LinearityCheck`."""

QUANTUM_CONSUMERS = (py.tuple.New, func.Invoke, func.Return, scf.For, scf.Yield)
"""The statements outside the wire dialect that can take a quantum operand."""


def _anchor(stmt: ir.Statement, region: ir.Region) -> ir.Statement | None:
    """Return the statement of `region` that holds `stmt`, or None if none holds it."""
    node: ir.Statement | None = stmt
    while node is not None and node.parent_region is not region:
        node = node.parent_stmt
    return node


def misuse(users: list[ir.Statement], region: ir.Region) -> str | None:
    """Return why the statements `users` break the use rule in `region`, or None.

    `users` holds one entry for each use of a linear value that `region` defines.
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
class LinearityCheck(CachedCalls[EmptyLattice]):
    """Record a validation error for each linear value that breaks the use rule."""

    keys = (KEY, "absint")
    lattice = EmptyLattice

    def method_self(self, method: ir.Method) -> EmptyLattice:
        """Return the top element for the method object."""
        return EmptyLattice.top()

    def error(self, node: ir.IRNode, message: str) -> None:
        """Record an ownership error at the operation that defines the value."""
        self.add_validation_error(node, ir.ValidationError(node, message))

    def check_uses(self, values: Iterable[ir.SSAValue], node: ir.IRNode) -> None:
        """Check one consuming use per quantum tuple field along each execution path."""
        for value in values:
            try:
                paths = linear_paths(value.type)
            except ValueError as error:
                self.error(node, str(error))
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
                        f"the linear value '{value.name or repr(value)}'{suffix} {reason}",
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
                field = self.tuple_field(user, value)
                if field is None or field != path[0]:
                    continue
                assert isinstance(value.type, types.Generic)
                if user.result.type != value.type.vars[field]:
                    self.error(
                        user, "Tuple extraction must preserve the quantum field type."
                    )
            elif not (
                user.dialect is stmts.dialect
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
        """Return the field of the tuple `value` that `user` reads.

        The result is None, and the check records an error, if the index is not a
        constant inside the tuple bounds.
        """
        index = constant_int(user.index)
        assert isinstance(value.type, types.Generic)
        size = len(value.type.vars)
        if index is None or not -size <= index < size:
            self.error(
                user, "A quantum tuple requires a constant index within its bounds."
            )
            return None
        return index % size

    def require_same_paths(
        self,
        node: ir.Statement,
        actual: types.TypeAttribute,
        declared: types.TypeAttribute,
    ) -> None:
        """Require a boundary type to retain every quantum ownership path."""
        try:
            if linear_paths(actual) != linear_paths(declared):
                self.error(node, "The boundary type must preserve every quantum field.")
        except ValueError as error:
            self.error(node, str(error))

    def frame_eval(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement
    ) -> interp.StatementResult[EmptyLattice]:
        """Check results before dispatch so every operation checks ownership."""
        if node.dialect is stmts.dialect and any(
            isinstance(value.type, types.BottomType)
            for value in (*node.args, *node.results)
        ):
            self.error(node, "A wire operation cannot use the impossible type Bottom.")
        self.check_uses(node.results, node)
        return super().frame_eval(frame, node)

    def require_flat(self, node: ir.Statement, values: Iterable[ir.SSAValue]) -> None:
        """Require control-flow state to carry each quantum value separately."""
        if any(
            contains_linear(value.type) and not is_linear(value.type)
            for value in values
        ):
            self.error(node, "Control flow requires separate wire and register values.")

    def frame_call(
        self,
        frame: ForwardFrame[EmptyLattice],
        node: ir.Statement,
        *args: EmptyLattice,
        **kwargs: EmptyLattice,
    ) -> EmptyLattice:
        """Check the parameters of the function `node`, then run its body."""
        trait = node.get_trait(ir.CallableStmtInterface)
        if trait is not None:
            params = trait.get_callable_region(node).blocks[0].args[1:]
            for value in params:
                if contains_linear(value.type) and not is_linear(value.type):
                    self.error(
                        node,
                        "Quantum function parameters must be separate wires or registers.",
                    )
            self.check_uses(params, node)
            if isinstance(node, func.Function):
                output = node.signature.output
                if isinstance(output, types.Generic) and is_subtype(
                    output, types.Tuple
                ):
                    if any(
                        contains_linear(kind) and not is_linear(kind)
                        for kind in output.vars
                    ):
                        self.error(
                            node,
                            "Quantum function outputs require a flat tuple of wires and registers.",
                        )
        return super().frame_call(frame, node, *args, **kwargs)

    def eval_fallback(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement
    ) -> tuple[EmptyLattice, ...]:
        """Check the results of a statement without a rule."""
        return tuple(EmptyLattice.top() for _ in node.results)


@py.tuple.dialect.register(key=KEY)
class _TupleLinearity(interp.MethodTable):
    """Check ownership types when an operation constructs a tuple."""

    @interp.impl(py.tuple.New)
    def new(
        self,
        check: LinearityCheck,
        frame: ForwardFrame[EmptyLattice],
        stmt: py.tuple.New,
    ) -> tuple[EmptyLattice, ...]:
        """Require each tuple field to retain its constructing operand's type."""
        expected = types.Generic(tuple, *(value.type for value in stmt.args))
        if contains_linear(expected) and stmt.result.type != expected:
            check.error(
                stmt, "Tuple construction must preserve every quantum field type."
            )
        return (EmptyLattice.top(),)


@func.dialect.register(key=KEY)
class _FunctionLinearity(interp.MethodTable):
    """Preserve quantum ownership through declared call and return types."""

    @interp.impl(func.Invoke)
    def invoke(
        self,
        check: LinearityCheck,
        frame: ForwardFrame[EmptyLattice],
        stmt: func.Invoke,
    ) -> tuple[EmptyLattice, ...]:
        """Check call types and validate the callee with Kirin's call machinery."""
        parameters = stmt.callee.callable_region.blocks[0].args[1:]
        for argument, parameter in zip(stmt.inputs, parameters):
            check.require_same_paths(stmt, argument.type, parameter.type)
        expected = stmt.callee.return_type
        if contains_linear(expected) and stmt.result.type != expected:
            check.error(
                stmt, "A call result must preserve its declared quantum field types."
            )
        check.call(
            stmt.callee.code,
            EmptyLattice.top(),
            *(EmptyLattice.top() for _ in parameters),
        )
        return (EmptyLattice.top(),)

    @interp.impl(func.Return)
    def return_(
        self,
        check: LinearityCheck,
        frame: ForwardFrame[EmptyLattice],
        stmt: func.Return,
    ) -> interp.ReturnValue[EmptyLattice]:
        """Require the function result type to retain its returned quantum fields."""
        owner = stmt.parent_stmt
        while owner is not None and not isinstance(owner, func.Function):
            owner = owner.parent_stmt
        if isinstance(owner, func.Function):
            check.require_same_paths(stmt, stmt.value.type, owner.signature.output)
        return interp.ReturnValue(EmptyLattice.top())


@scf.dialect.register(key=KEY)
class _Scf(interp.MethodTable):
    """Check the results and the block arguments of loops and branches."""

    @interp.impl(scf.For)
    @interp.impl(scf.IfElse)
    def structured(
        self,
        check: LinearityCheck,
        frame: ForwardFrame[EmptyLattice],
        stmt: ir.Statement,
    ) -> tuple[EmptyLattice, ...]:
        """Check the state types, then run each body once."""
        check.require_flat(stmt, stmt.results)
        if isinstance(stmt, scf.For):
            check.require_flat(stmt, stmt.initializers)
            for value, argument in zip(stmt.initializers, stmt.body.blocks[0].args[1:]):
                check.require_same_paths(stmt, value.type, argument.type)
        for region in stmt.regions:
            if not region.blocks:
                continue
            block = region.blocks[0]
            check.check_uses(block.args, stmt)
            args = [EmptyLattice.top() for _ in block.args]
            with check.new_frame(stmt, has_parent_access=True) as inner:
                check.frame_call_region(inner, stmt, region, *args)
        return tuple(EmptyLattice.top() for _ in stmt.results)

    @interp.impl(scf.Yield)
    def yield_(
        self, check: LinearityCheck, frame: ForwardFrame[EmptyLattice], stmt: scf.Yield
    ) -> interp.YieldValue[EmptyLattice]:
        """Check yielded ownership against each declared region result."""
        check.require_flat(stmt, stmt.values)
        if stmt.parent_stmt is not None:
            for value, result in zip(stmt.values, stmt.parent_stmt.results):
                check.require_same_paths(stmt, value.type, result.type)
        return interp.YieldValue(tuple(EmptyLattice.top() for _ in stmt.values))


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

    def check(self, method: ir.Method) -> None:
        """Raise a `ValidationErrorGroup` if `method` breaks a linearity rule."""
        _, errors = self.run(method)
        if errors:
            raise ValidationErrorGroup(
                f"'{method.sym_name}' breaks {len(errors)} linearity rules.", errors
            )
