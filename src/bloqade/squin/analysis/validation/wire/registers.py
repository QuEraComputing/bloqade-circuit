"""Check that every wire leaves its register and comes back to the same place.

`RegisterAnalysis` gives each wire and register value a `Place`. A place names the
allocation that the value comes from, which is its root. A register place also holds
its length and its holes, which are the elements that a `Borrow`, a `Take` or a
`TakeSlice` took out.

The analysis records these errors:
- A statement takes an element that is already out of its register.
- A `Release` puts back a wire that came from another element.
- A register with holes leaves through a free, a yield, a return or a call.
- A loop, a branch or an in-out function moves a qubit to another position.

A register place that the analysis cannot name is `Unknown`. A borrow or a release
on such a register records nothing. The next statement that needs a complete
register then reports it.
"""

from __future__ import annotations

from typing import Union, TypeAlias
from dataclasses import field, replace, dataclass
from collections.abc import Iterable

from kirin import ir, interp
from kirin.lattice import BoundedLattice
from kirin.dialects import py, scf, func
from kirin.validation import ValidationPass
from typing_extensions import Self
from kirin.analysis.forward import ForwardFrame

from bloqade.types import is_subtype
from bloqade.squin.wire import state, stmts
from bloqade.analysis.indices import Sym, Slice, Indices, IndexExpr
from bloqade.squin.wire.types import WireType, RegisterType, is_linear, register_length
from bloqade.squin.wire.traits import Threads
from bloqade.squin.wire.returns import ReturnPolicy, return_policy

from .calls import CachedCalls

KEY: str = "squin.wire.registers"
"""Name the registry key of the method tables of `RegisterAnalysis`."""


@dataclass(frozen=True)
class Part:
    """Name the range of the register `register` that starts at `start`.

    A `TakeSlice` gives its slice register this root.
    """

    register: Root
    start: IndexExpr


@dataclass(frozen=True)
class Fresh:
    """Name the allocation `root` of a callee as the call `call` returns it.

    Two calls of one callee return different allocations.
    """

    call: ir.Statement
    root: Root


Root: TypeAlias = Union[ir.SSAValue, Part, Fresh]
"""Name one allocation by the value that made it."""


@dataclass(frozen=True)
class Borrowed:
    """Keep the borrowed span and its original place across changes to other elements."""

    span: Slice
    origin: Place


@dataclass(frozen=True)
class Moved:
    """Name the elements `span` that a `Take` or a `TakeSlice` moved out for good."""

    span: Slice


Hole: TypeAlias = Borrowed | Moved
"""Name elements that a register lacks now."""


@dataclass(frozen=True)
class Place(BoundedLattice["Place"]):
    """Hold what the analysis knows about where a value comes from.

    `Unknown` is the top and `Unreachable` is the bottom. `Standalone`, `Element`
    and `Register` name the place of a wire or a register, and `Fields` holds one
    place for each field of a tuple.
    """

    @classmethod
    def top(cls) -> Place:
        """Return the place of a value that the analysis cannot name."""
        return Unknown()

    @classmethod
    def bottom(cls) -> Place:
        """Return the place of a value that no execution reaches."""
        return Unreachable()

    def is_subseteq(self, other: Place) -> bool:
        """Check whether every fact of `other` also holds for `self`."""
        if isinstance(self, Unreachable) or isinstance(other, Unknown) or self == other:
            return True
        if isinstance(self, Register) and isinstance(other, Register):
            return (
                other.root in (None, self.root)
                and other.length in (None, self.length)
                and self.holes <= other.holes
                and (
                    other.items is None
                    or (
                        self.items is not None
                        and len(self.items) == len(other.items)
                        and all(
                            a.is_subseteq(b) for a, b in zip(self.items, other.items)
                        )
                    )
                )
            )
        return (
            isinstance(self, Fields)
            and isinstance(other, Fields)
            and len(self.items) == len(other.items)
            and all(a.is_subseteq(b) for a, b in zip(self.items, other.items))
        )

    def join(self, other: Place) -> Place:
        """Return the facts that hold for both values."""
        if self.is_subseteq(other):
            return other
        if other.is_subseteq(self):
            return self
        if isinstance(self, Register) and isinstance(other, Register):
            return Register(
                self.root if self.root == other.root else None,
                self.length if self.length == other.length else None,
                self.holes | other.holes,
                (
                    tuple(a.join(b) for a, b in zip(self.items, other.items))
                    if self.items is not None
                    and other.items is not None
                    and len(self.items) == len(other.items)
                    else None
                ),
            )
        if (
            isinstance(self, Fields)
            and isinstance(other, Fields)
            and len(self.items) == len(other.items)
        ):
            return Fields(tuple(a.join(b) for a, b in zip(self.items, other.items)))
        return Unknown()

    def meet(self, other: Place) -> Place:
        """Return the facts of both values, or `Unreachable` if they conflict."""
        if self.is_subseteq(other):
            return self
        if other.is_subseteq(self):
            return other
        if isinstance(self, Register) and isinstance(other, Register):
            root = self.root if other.root is None else other.root
            length = self.length if other.length is None else other.length
            if (self.root not in (None, root)) or (self.length not in (None, length)):
                return Unreachable()
            if self.items is None:
                items = other.items
            elif other.items is None:
                items = self.items
            elif len(self.items) == len(other.items):
                items = tuple(a.meet(b) for a, b in zip(self.items, other.items))
            else:
                return Unreachable()
            return Register(root, length, self.holes & other.holes, items)
        if (
            isinstance(self, Fields)
            and isinstance(other, Fields)
            and len(self.items) == len(other.items)
        ):
            return Fields(tuple(a.meet(b) for a, b in zip(self.items, other.items)))
        return Unreachable()

    def roots(self) -> frozenset[Root]:
        """Return the allocations that this place names."""
        if isinstance(self, (Standalone, Element)):
            return frozenset({self.root})
        if isinstance(self, Register):
            return (
                frozenset() if self.root is None else frozenset({self.root})
            ) | frozenset(root for item in self.items or () for root in item.roots())
        if isinstance(self, Fields):
            return frozenset(root for item in self.items for root in item.roots())
        return frozenset()

    def at_call(self, call: ir.Statement, inputs: frozenset[Root]) -> Place:
        """Give each allocation that a call makes a root of its own.

        An allocation that the caller passed in keeps its root.
        """
        if isinstance(self, Fields):
            return Fields(tuple(item.at_call(call, inputs) for item in self.items))
        if isinstance(self, Register):
            root = (
                Fresh(call, self.root)
                if self.root is not None and self.root not in inputs
                else self.root
            )
            items = (
                None
                if self.items is None
                else tuple(item.at_call(call, inputs) for item in self.items)
            )
            return replace(self, root=root, items=items)
        if isinstance(self, (Standalone, Element)) and (
            self.root is not None and self.root not in inputs
        ):
            return replace(self, root=Fresh(call, self.root))
        return self


@dataclass(frozen=True)
class Unknown(Place):
    """Name a value whose place the analysis cannot name."""


@dataclass(frozen=True)
class Unreachable(Place):
    """Name a value that no execution reaches."""


@dataclass(frozen=True)
class Standalone(Place):
    """Name the wire of the standalone qubit `root`."""

    root: Root


@dataclass(frozen=True)
class Element(Place):
    """Name the wire of element `index` of the register `root`."""

    root: Root
    index: IndexExpr


@dataclass(frozen=True)
class Register(Place):
    """Name the register `root` with `length` elements and the holes `holes`.

    `root` is None after a loop or a branch joins two different registers.
    `length` is None if the analysis cannot name the length.
    """

    root: Root | None
    length: IndexExpr | None = None
    holes: frozenset[Hole] = frozenset()
    items: tuple[Place, ...] | None = None
    """Preserve each packed wire's origin when the register has a known layout."""


@dataclass(frozen=True)
class Fields(Place):
    """Hold the place of each field of a tuple."""

    items: tuple[Place, ...]


def unnamed(value: ir.SSAValue) -> Place:
    """Return the place of a value whose origin the analysis cannot trace.

    A register gets a complete register of its own root, because every register
    that crosses a call, a tuple or a region has no holes.
    """
    if is_subtype(value.type, RegisterType):
        return Register(value)
    return Unknown()


def named(place: Place, value: ir.SSAValue) -> Place:
    """Give a register place without a root the root `value`.

    A loop or a branch that joins 2 different registers gives its result this root.
    """
    if isinstance(place, Register) and place.root is None:
        return replace(place, root=value)
    return place


def made(value: ir.SSAValue, length: IndexExpr | None = None) -> Place:
    """Return the place of the new allocation that `value` names."""
    if value.type == WireType:
        return Standalone(value)
    return Register(value, length)


def position(register: Register, index: IndexExpr) -> IndexExpr:
    """Return the element position of `index`, which counts from 0.

    A negative constant index counts from the end of a register of known length.
    """
    if (at := index.constant) is not None and at < 0 and register.length is not None:
        return register.length + index
    return index


def element(register: Register, index: IndexExpr) -> Place:
    """Return the place of the element at the position `index` of `register`.

    The result is `Unknown` for a negative position, for a position outside the
    known length and for a register without a root.
    """
    at = index.constant
    size = None if register.length is None else register.length.constant
    if register.root is None or (at is not None and at < 0):
        return Unknown()
    if size is not None and at is not None and at >= size:
        return Unknown()
    if register.items is not None and at is not None and at < len(register.items):
        return register.items[at]
    return Element(register.root, index)


def overlaps(a: Hole, b: Hole) -> bool:
    """Check whether two holes provably share a register element.

    Holes whose overlap depends on runtime values pass. A source program must keep
    such holes apart, as it must keep a runtime index inside its register.
    """
    left, right = a.span, b.span
    if left.length is None or right.length is None:
        return False
    # The ranges `[s1, s1 + n1)` and `[s2, s2 + n2)` meet if each one starts before
    # the other one ends.
    gaps = (
        (left.start + left.length - right.start).constant,
        (right.start + right.length - left.start).constant,
    )
    return all(gap is not None and gap > 0 for gap in gaps)


def one(index: IndexExpr) -> Slice:
    """Return the span of the single element `index`."""
    return Slice(index, 1, IndexExpr(1))


def fill_moved(holes: frozenset[Hole], span: Slice) -> frozenset[Hole] | None:
    """Subtract a filled span from taken ranges, or return None if coverage is uncertain.

    Constant offsets from the filled span let adjacent holes cover one insertion.
    A partial insertion leaves the unfilled parts as separate holes.
    """
    size = None if span.length is None else span.length.constant
    if size is None or size < 0:
        return None
    if size == 0:
        return holes
    ranges: list[tuple[int, int, Moved]] = []
    for hole in holes:
        if not isinstance(hole, Moved) or hole.span.length is None:
            continue
        offset = (hole.span.start - span.start).constant
        length = hole.span.length.constant
        if (
            offset is not None
            and length is not None
            and offset < size
            and offset + length > 0
        ):
            ranges.append((offset, offset + length, hole))
    remaining = set(holes)
    covered = 0
    for start, stop, hole in sorted(ranges, key=lambda item: item[0]):
        if start > covered:
            return None
        covered = max(covered, stop)
        remaining.remove(hole)
        if start < 0:
            remaining.add(Moved(Slice(hole.span.start, 1, IndexExpr(-start))))
        if stop > size:
            remaining.add(
                Moved(Slice(span.start + IndexExpr(size), 1, IndexExpr(stop - size)))
            )
    return frozenset(remaining) if covered >= size else None


@dataclass
class RegisterAnalysis(CachedCalls[Place]):
    """Record a validation error for each wire that leaves its place."""

    keys = (KEY,)
    lattice = Place
    max_loop_iterations: int = 32
    """Limit loop analysis visits and reject a loop if its facts still change."""
    active_functions: list[ir.Statement] = field(default_factory=list, init=False)
    """Hold the functions that the analysis interprets now, innermost last."""
    return_policies: dict[ir.Statement, ReturnPolicy] = field(
        default_factory=dict, kw_only=True
    )
    """Override the return policy of each listed function for this analysis."""
    indices: Indices = field(init=False)
    """Hold the index expression of each integer value, computed once per function."""
    lengths: dict[Sym, IndexExpr] = field(default_factory=dict, init=False)
    """Hold the known register length that each `Length` result reads.

    The `Length` rule fills this table. Forward analysis visits a definition before
    each of its uses, so every index expression can use the table.
    """

    def initialize(self) -> Self:
        """Forget the functions, the indices and the lengths of the previous run."""
        super().initialize()
        self.active_functions = []
        self.indices = Indices(self.dialects)
        self.lengths = {}
        return self

    def index(self, value: ir.SSAValue) -> IndexExpr:
        """Return the index expression of `value` with the known register lengths."""
        return self.indices.of(value).substitute(self.lengths)

    def method_self(self, method: ir.Method) -> Place:
        """Return an unknown place for the function object."""
        return Unknown()

    def error(self, node: ir.IRNode, message: str) -> None:
        """Record the validation error `message` at `node`."""
        self.add_validation_error(node, ir.ValidationError(node, message))

    def expect(
        self, node: ir.Statement, actual: Place, expected: Place, message: str
    ) -> None:
        """Record `message` at `node` unless both places name the same allocation."""
        if not actual.roots() or actual != expected:
            self.error(node, message)

    def expect_complete(
        self,
        frame: ForwardFrame[Place],
        node: ir.Statement,
        values: Iterable[ir.SSAValue],
    ) -> None:
        """Record an error at `node` for each register of `values` with a hole."""
        for value in values:
            if not is_subtype(value.type, RegisterType):
                continue
            place = frame.get(value)
            if isinstance(place, Unknown):
                self.error(
                    node, f"'{node.name}' takes a register that the check cannot name."
                )
            elif isinstance(place, Register) and place.holes:
                self.error(
                    node, f"'{node.name}' takes a register with an element out of it."
                )

    def open_hole(self, stmt: ir.Statement, register: Place, hole: Hole) -> Place:
        """Return `register` with the hole `hole`, and check that the hole is free.

        Any other place than a register stays as it is.
        """
        if not isinstance(register, Register):
            return register
        span = hole.span
        size = None if span.length is None else span.length.constant
        start = span.start.constant
        rest = (
            None
            if register.length is None or span.length is None
            else (register.length - span.start - span.length).constant
        )
        if (
            (size is not None and size < 0)
            or (register.length is not None and start is not None and start < 0)
            or (rest is not None and rest < 0)
        ):
            self.error(stmt, "The transfer range must lie within the register bounds.")
        if any(overlaps(hole, other) for other in register.holes):
            self.error(
                stmt,
                f"'{stmt.name}' takes an element that is already out of its register.",
            )
        return replace(register, holes=register.holes | {hole})

    def close_hole(
        self, stmt: ir.Statement, register: Register, hole: Hole, message: str
    ) -> Register:
        """Fill a matching borrow or a covered taken range, and report a missing hole."""
        if hole in register.holes:
            return replace(register, holes=register.holes - {hole})
        if isinstance(hole, Moved):
            remaining = fill_moved(register.holes, hole.span)
            if remaining is not None:
                return replace(register, holes=remaining)
        self.error(stmt, message)
        return register

    @property
    def checks_positions(self) -> bool:
        """Check whether the innermost function keeps its qubits in position.

        `PreserveArguments` keeps each quantum parameter in its return position.
        Its loops and branches must also keep each qubit in its position.
        Analysis overrides apply to their listed functions.
        """
        function = self.active_functions[-1]
        if not isinstance(function, func.Function):
            return True
        policy = self.return_policies.get(function, return_policy(function))
        return policy is ReturnPolicy.PreserveArguments

    def frame_call(
        self,
        frame: ForwardFrame[Place],
        node: ir.Statement,
        *args: Place,
        **kwargs: Place,
    ) -> Place:
        """Interpret the function body, then check its return suffix."""
        self.active_functions.append(node)
        try:
            result = super().frame_call(frame, node, *args, **kwargs)
            if self.checks_positions:
                self.check_return_suffix(frame, node, result)
            return result
        finally:
            self.active_functions.pop()

    def check_return_suffix(
        self, frame: ForwardFrame[Place], node: ir.Statement, result: Place
    ) -> None:
        """Require the last results of `node` to continue its quantum parameters in order."""
        region = node.get_present_trait(ir.CallableStmtInterface).get_callable_region(
            node
        )
        parameters = [arg for arg in region.blocks[0].args[1:] if is_linear(arg.type)]
        outputs = result.items if isinstance(result, Fields) else (result,)
        end = region.blocks[0].last_stmt
        assert end is not None
        if len(outputs) < len(parameters):
            self.error(end, "The return must end with every in-out parameter.")
            return
        if not parameters:
            return
        for i, (actual, parameter) in enumerate(
            zip(outputs[-len(parameters) :], parameters)
        ):
            self.expect(
                end,
                actual,
                frame.get(parameter),
                f"Return suffix position {i} must continue in-out parameter {i}.",
            )

    def eval_fallback(
        self, frame: ForwardFrame[Place], node: ir.Statement
    ) -> tuple[Place, ...]:
        """Require complete register operands, and keep the place of each thread.

        A result that continues an operand, such as the output of a `RegisterGate`,
        keeps the place of that operand.
        """
        self.expect_complete(frame, node, node.args)
        places = {result: unnamed(result) for result in node.results}
        if (threads := node.get_trait(Threads)) is not None:
            for operand, result in threads.threads(node):
                places[result] = frame.get(operand)
        return tuple(places.values())


@state.dialect.register(key=KEY)
class Registers(interp.MethodTable):
    """Track places and holes through allocations, borrows and moves."""

    @interp.impl(stmts.Alloc)
    def alloc(
        self, check: RegisterAnalysis, frame: ForwardFrame[Place], stmt: stmts.Alloc
    ) -> tuple[Place, ...]:
        """Name the new qubit."""
        return (Standalone(stmt.result),)

    @interp.impl(stmts.AllocRegister)
    def alloc_register(
        self,
        check: RegisterAnalysis,
        frame: ForwardFrame[Place],
        stmt: stmts.AllocRegister,
    ) -> tuple[Place, ...]:
        """Name the new register and its length."""
        length = check.index(stmt.size)
        if (size := length.constant) is not None and size < 0:
            check.error(stmt, "Register allocation size must be nonnegative.")
        return (Register(stmt.result, length),)

    @interp.impl(stmts.PackRegister)
    def pack(
        self,
        check: RegisterAnalysis,
        frame: ForwardFrame[Place],
        stmt: stmts.PackRegister,
    ) -> tuple[Place, ...]:
        """Name the new register of the packed wires."""
        return (
            Register(
                stmt.result,
                IndexExpr(len(stmt.wires)),
                items=frame.get_values(stmt.wires),
            ),
        )

    @interp.impl(stmts.Take)
    @interp.impl(stmts.Borrow)
    def borrow(
        self,
        check: RegisterAnalysis,
        frame: ForwardFrame[Place],
        stmt: stmts.Borrow | stmts.Take,
    ) -> tuple[Place, ...]:
        """Add a hole at the index, and name the wire as that element."""
        register = frame.get(stmt.register)
        if not isinstance(register, Register):
            return register, register
        at = position(register, check.index(stmt.index))
        origin = element(register, at)
        hole = (
            Moved(one(at))
            if isinstance(stmt, stmts.Take)
            else Borrowed(one(at), origin)
        )
        opened = check.open_hole(stmt, register, hole)
        return opened, origin

    @interp.impl(stmts.Release)
    def release(
        self, check: RegisterAnalysis, frame: ForwardFrame[Place], stmt: stmts.Release
    ) -> tuple[Place, ...]:
        """Remove the hole at the index, and require the wire of that element."""
        register = frame.get(stmt.register)
        if not isinstance(register, Register):
            return (register,)
        at = position(register, check.index(stmt.index))
        hole = next(
            (
                hole
                for hole in register.holes
                if isinstance(hole, Borrowed) and hole.span == one(at)
            ),
            Borrowed(one(at), Unknown()),
        )
        check.expect(
            stmt,
            frame.get(stmt.wire),
            hole.origin,
            "A release must put back the qubit of its register element.",
        )
        message = "'release' requires a borrowed element at its index."
        return (check.close_hole(stmt, register, hole, message),)

    @interp.impl(stmts.Put)
    def put(
        self, check: RegisterAnalysis, frame: ForwardFrame[Place], stmt: stmts.Put
    ) -> tuple[Place, ...]:
        """Fill the taken element at the index, which makes the register a new one."""
        register = frame.get(stmt.register)
        if not isinstance(register, Register):
            return (register,)
        at = position(register, check.index(stmt.index))
        message = "'put' requires a taken element at its index."
        closed = check.close_hole(stmt, register, Moved(one(at)), message)
        items = None
        if (
            closed.items is not None
            and at.constant is not None
            and 0 <= at.constant < len(closed.items)
        ):
            values = list(closed.items)
            values[at.constant] = frame.get(stmt.wire)
            items = tuple(values)
        return (replace(closed, root=stmt.register_out, items=items),)

    @interp.impl(stmts.Length)
    def length(
        self, check: RegisterAnalysis, frame: ForwardFrame[Place], stmt: stmts.Length
    ) -> tuple[Place, ...]:
        """Keep the register, and record its known length for later indices.

        The rule clears an entry of an earlier call of the same function, so that
        each call reads only its own register length.
        """
        register = frame.get(stmt.register)
        if isinstance(register, Register) and register.length is not None:
            check.lengths[stmt.result] = register.length
        else:
            check.lengths.pop(stmt.result, None)
        return register, Unknown()

    @interp.impl(stmts.SplitRegister)
    def split(
        self,
        check: RegisterAnalysis,
        frame: ForwardFrame[Place],
        stmt: stmts.SplitRegister,
    ) -> tuple[Place, ...]:
        """Require a complete register, and name the two new parts."""
        check.expect_complete(frame, stmt, stmt.args)
        register = frame.get(stmt.register)
        at = check.index(stmt.index)
        length = register.length if isinstance(register, Register) else None
        rest = None if length is None else length - at
        if (at.constant is not None and at.constant < 0) or (
            rest is not None and rest.constant is not None and rest.constant < 0
        ):
            check.error(
                stmt, "The split index must lie between zero and the register length."
            )
        items = register.items if isinstance(register, Register) else None
        left = None if items is None or at.constant is None else items[: at.constant]
        right = None if items is None or at.constant is None else items[at.constant :]
        return Register(stmt.results[0], at, items=left), Register(
            stmt.results[1], rest, items=right
        )

    @interp.impl(stmts.JoinRegister)
    def join(
        self,
        check: RegisterAnalysis,
        frame: ForwardFrame[Place],
        stmt: stmts.JoinRegister,
    ) -> tuple[Place, ...]:
        """Require complete registers, and name the new register of both."""
        check.expect_complete(frame, stmt, stmt.args)
        a, b = (
            place.length if isinstance(place, Register) else None
            for place in frame.get_values(stmt.args)
        )
        left, right = frame.get_values(stmt.args)
        items = (
            left.items + right.items
            if (
                isinstance(left, Register)
                and isinstance(right, Register)
                and left.items is not None
                and right.items is not None
            )
            else None
        )
        return (
            Register(
                stmt.result, None if a is None or b is None else a + b, items=items
            ),
        )

    @interp.impl(stmts.TakeSlice)
    def take_slice(
        self,
        check: RegisterAnalysis,
        frame: ForwardFrame[Place],
        stmt: stmts.TakeSlice,
    ) -> tuple[Place, ...]:
        """Add a taken range, and name the slice register as that part."""
        register = frame.get(stmt.register)
        size = check.index(stmt.length)
        if not isinstance(register, Register):
            return register, Register(stmt.slice_register, size)
        start = position(register, check.index(stmt.start))
        opened = check.open_hole(stmt, register, Moved(Slice(start, 1, size)))
        root = None if register.root is None else Part(register.root, start)
        items = None
        if (
            register.items is not None
            and start.constant is not None
            and size.constant is not None
        ):
            items = register.items[start.constant : start.constant + size.constant]
        return opened, Register(root or stmt.slice_register, size, items=items)

    @interp.impl(stmts.PutSlice)
    def put_slice(
        self, check: RegisterAnalysis, frame: ForwardFrame[Place], stmt: stmts.PutSlice
    ) -> tuple[Place, ...]:
        """Fill a taken range with a complete slice of the same length.

        The register keeps its root if the slice returns to the range that it left.
        A slice from anywhere else, such as in the register surgery that Jeff import
        produces, makes the register a new one.
        """
        check.expect_complete(frame, stmt, (stmt.slice_register,))
        register = frame.get(stmt.register)
        if not isinstance(register, Register):
            return (register,)
        part = frame.get(stmt.slice_register)
        size = part.length if isinstance(part, Register) else None
        start = position(register, check.index(stmt.start))
        message = "A slice insertion must fill a taken range of the same length."
        if size is None:
            check.error(stmt, message)
            return (Register(stmt.register_out, register.length),)
        closed = check.close_hole(stmt, register, Moved(Slice(start, 1, size)), message)
        items = None
        if (
            closed.items is not None
            and isinstance(part, Register)
            and part.items is not None
            and start.constant is not None
            and size.constant is not None
        ):
            items = (
                closed.items[: start.constant]
                + part.items
                + closed.items[start.constant + size.constant :]
            )
        closed = replace(closed, items=items)
        if (
            isinstance(part, Register)
            and register.root is not None
            and part.root == Part(register.root, start)
        ):
            return (closed,)
        return (replace(closed, root=stmt.register_out),)

    @interp.impl(stmts.DiscardRegister)
    def discard(
        self,
        check: RegisterAnalysis,
        frame: ForwardFrame[Place],
        stmt: stmts.DiscardRegister,
    ) -> tuple[Place, ...]:
        """Allow moved elements, and require every borrowed element back."""
        register = frame.get(stmt.register)
        if isinstance(register, Unknown) or (
            isinstance(register, Register)
            and any(isinstance(hole, Borrowed) for hole in register.holes)
        ):
            check.error(
                stmt, "A discarded register must get back every borrowed element."
            )
        return ()


@py.assign.dialect.register(key=KEY)
class Aliases(interp.MethodTable):
    """Keep places across aliases."""

    @interp.impl(py.assign.Alias)
    def alias(
        self, check: RegisterAnalysis, frame: ForwardFrame[Place], stmt: py.assign.Alias
    ) -> tuple[Place, ...]:
        """Require a complete register, and return the place of the operand."""
        check.expect_complete(frame, stmt, stmt.args)
        return (frame.get(stmt.value),)


@py.tuple.dialect.register(key=KEY)
class Tuples(interp.MethodTable):
    """Keep a separate place for each tuple field."""

    @interp.impl(py.tuple.New)
    def new(
        self, check: RegisterAnalysis, frame: ForwardFrame[Place], stmt: py.tuple.New
    ) -> tuple[Place, ...]:
        """Require complete registers, and collect the places of the fields in order."""
        check.expect_complete(frame, stmt, stmt.args)
        return (Fields(frame.get_values(stmt.args)),)


@py.indexing.dialect.register(key=KEY)
class Indexing(interp.MethodTable):
    """Read the place of a known tuple field."""

    @interp.impl(py.GetItem)
    def getitem(
        self, check: RegisterAnalysis, frame: ForwardFrame[Place], stmt: py.GetItem
    ) -> tuple[Place, ...]:
        """Return the place of the field at a known integer index."""
        obj = frame.get(stmt.obj)
        index = check.indices.of(stmt.index).constant
        if (
            isinstance(obj, Fields)
            and index is not None
            and -len(obj.items) <= index < len(obj.items)
        ):
            return (obj.items[index],)
        return (unnamed(stmt.result),)


@func.dialect.register(key=KEY)
class Functions(interp.MethodTable):
    """Check calls and returns, and keep the place of each call result."""

    @interp.impl(func.Invoke)
    def invoke(
        self, check: RegisterAnalysis, frame: ForwardFrame[Place], stmt: func.Invoke
    ) -> tuple[Place, ...]:
        """Run the callee on the argument places, and name its new allocations.

        The rule reports a recursive call before Kirin's call machinery runs, because
        that machinery answers a recursive call with the bottom place.
        """
        check.expect_complete(frame, stmt, stmt.args)
        if stmt.callee.code in check.active_functions:
            check.error(stmt, "Wire validation does not support recursive calls.")
            return (unnamed(stmt.result),)
        inputs = frame.get_values(stmt.inputs)
        _, result = check.call(stmt.callee.code, Unknown(), *inputs)
        roots = frozenset(root for value in inputs for root in value.roots())
        return (result.at_call(stmt, roots),)

    @interp.impl(func.Return)
    def return_(
        self, check: RegisterAnalysis, frame: ForwardFrame[Place], stmt: func.Return
    ) -> interp.ReturnValue[Place]:
        """Require complete registers, and return the place of the value."""
        check.expect_complete(frame, stmt, stmt.args)
        return interp.ReturnValue(frame.get(stmt.value))


@scf.dialect.register(key=KEY)
class ControlFlow(interp.MethodTable):
    """Check loop invariants and branch results, and keep qubits in position."""

    @interp.impl(scf.Yield)
    def yield_(
        self, check: RegisterAnalysis, frame: ForwardFrame[Place], stmt: scf.Yield
    ) -> interp.YieldValue[Place]:
        """Require complete registers, and return the yielded places."""
        check.expect_complete(frame, stmt, stmt.values)
        return interp.YieldValue(frame.get_values(stmt.values))

    @interp.impl(scf.For)
    def loop(
        self, check: RegisterAnalysis, frame: ForwardFrame[Place], stmt: scf.For
    ) -> tuple[Place, ...]:
        """Check the body until the joined input and output places stop changing.

        Each visit uses a fresh frame so that earlier lengths cannot constrain later
        iterations. A register with changing roots gets the loop argument as its root.
        """
        check.expect_complete(frame, stmt, stmt.args)
        candidate = frame.get_values(stmt.initializers)
        arguments = stmt.body.blocks[0].args[1:]
        end = stmt.body.blocks[0].last_stmt
        assert isinstance(end, scf.Yield)
        for _ in range(check.max_loop_iterations):
            inputs = tuple(
                named(place, arg) for place, arg in zip(candidate, arguments)
            )
            with check.new_frame(stmt, has_parent_access=True) as body:
                yielded = check.frame_call_region(
                    body, stmt, stmt.body, Unknown(), *inputs
                )
            assert isinstance(yielded, tuple)
            for i, (argument, actual, expected) in enumerate(
                zip(arguments, yielded, inputs)
            ):
                if check.checks_positions and is_linear(argument.type):
                    check.expect(
                        end,
                        actual,
                        expected,
                        f"Yield position {i} must continue loop input position {i}.",
                    )
            joined = tuple(
                before.join(after) for before, after in zip(candidate, yielded)
            )
            if joined == candidate:
                return tuple(
                    named(place, result) for place, result in zip(joined, stmt.results)
                )
            candidate = joined
        check.error(
            stmt,
            f"Register loop analysis did not converge within {check.max_loop_iterations} iterations.",
        )
        return tuple(Unknown() for _ in stmt.results)

    @interp.impl(scf.IfElse)
    def branch(
        self, check: RegisterAnalysis, frame: ForwardFrame[Place], stmt: scf.IfElse
    ) -> tuple[Place, ...]:
        """Require both branches to continue the same qubit at each yield position."""
        check.expect_complete(frame, stmt, stmt.args)
        yielded: list[tuple[Place, ...]] = []
        for region in (stmt.then_body, stmt.else_body):
            if not region.blocks:
                yielded.append(tuple(unnamed(result) for result in stmt.results))
                continue
            with check.new_frame(stmt, has_parent_access=True) as body:
                result = check.frame_call_region(
                    body, stmt, region, *(unnamed(arg) for arg in region.blocks[0].args)
                )
            assert isinstance(result, tuple)
            yielded.append(result)
        left, right = yielded
        for i, (value, first, second) in enumerate(zip(stmt.results, left, right)):
            if check.checks_positions and is_linear(value.type):
                check.expect(
                    stmt,
                    second,
                    first,
                    f"Both branches must continue the same qubit at yield position {i}.",
                )
        return tuple(
            named(first.join(second), result)
            for first, second, result in zip(left, right, stmt.results)
        )


def parameter(argument: ir.BlockArgument) -> Place:
    """Return the place of a function parameter, with the length of its type."""
    if is_linear(argument.type):
        length = register_length(argument.type)
        return made(argument, None if length is None else IndexExpr(length))
    return Unknown()


@dataclass
class RegisterValidation(ValidationPass[ForwardFrame[Place]]):
    """Check that each wire comes back to its place before its register leaves."""

    return_policy: ReturnPolicy | None = field(default=None, kw_only=True)
    """Override the root function's policy while each callee keeps its declared policy."""

    def name(self) -> str:
        """Return the pass name that validation reports show."""
        return "squin wire registers"

    def run(
        self, method: ir.Method
    ) -> tuple[ForwardFrame[Place], list[ir.ValidationError]]:
        """Run `RegisterAnalysis` with a root of its own for each quantum parameter."""
        check = RegisterAnalysis(method.dialects)
        if self.return_policy is not None:
            check.return_policies[method.code] = self.return_policy
        inputs = tuple(
            parameter(arg) for arg in method.callable_region.blocks[0].args[1:]
        )
        frame, _ = check.run(method, *inputs)
        return frame, check.get_validation_errors()
