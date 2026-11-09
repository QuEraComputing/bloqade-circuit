"""Emit fresh wire IR while Kirin visits unchanged source operations."""

from typing import TypeVar
from dataclasses import field, replace, dataclass
from collections.abc import Mapping, Callable, Sequence

from kirin import ir, types
from kirin.emit import EmitABC, EmitFrame
from kirin.dialects import py, func
from kirin.emit.abc import EmitTable
from kirin.worklist import WorkList
from kirin.dialects.py.len import Len

from bloqade.types import holds_qubits
from bloqade.squin.wire import stmts
from bloqade.analysis.indices import Sym, Iter, Slice, Indices, IndexExpr
from bloqade.squin.wire.group import WIRE_DIALECTS
from bloqade.squin.wire.traits import Threads

from .values import (
    View,
    Qubit,
    Value,
    Single,
    Element,
    Location,
    Register,
    WrapperSelf,
    singles,
    row_width,
    known_items,
    contains_location,
)

StatementT = TypeVar("StatementT", bound=ir.Statement)


@dataclass
class WireFrame(EmitFrame[Value]):
    """Hold the emission state of one source region.

    The inherited `entries` map each source value to its meaning, such as a quantum
    `Location`. The frame adds the wire state: the block it emits, the latest wire of
    each allocation and the allocations to free at its end.
    """

    output: ir.Block = field(default_factory=ir.Block)
    """Hold the wire block that this frame emits."""
    latest: dict[ir.SSAValue, ir.SSAValue] = field(default_factory=dict)
    """Hold the latest wire or register value of each allocation root.

    An operation that consumes a qubit replaces the entry of its root. A root has
    no entry while an operation holds its whole value.
    """
    local_roots: list[Qubit | Register] = field(default_factory=list)
    """Hold the allocations that this region made and must free at its end."""
    site: func.Invoke | None = None
    """Hold the user call that runs the library wrapper of this frame, or None in user code.

    Each operation that a library wrapper emits takes its source location from this
    call, so that diagnostics point at user code.
    """

    @property
    def statement(self) -> ir.Statement:
        """Return the source statement that the frame emits now.

        Before the first statement of its region, the frame names its own code.
        """
        return self.current_stmt or self.code

    def share(self, caller: "WireFrame", call: func.Invoke) -> None:
        """Emit into the block of `caller` and continue its wires and allocations.

        The body of a library wrapper uses this, so each wrapper call emits its body
        in place of the call.
        """
        self.site = caller.site or call
        self.output = caller.output
        self.latest = caller.latest
        self.local_roots = caller.local_roots

    def own(self, location: Qubit | Register, local: bool = True) -> None:
        """Start the wire state of the allocation `location`.

        If `local` is True, the region frees the allocation at its end.
        """
        self.latest[location.root] = location.root
        if local:
            self.local_roots.append(location)

    def push(self, node: StatementT) -> StatementT:
        """Append an operation and give it the source location of the current operation."""
        source = self.site or self.current_stmt
        if source is not None and source.source is not None:
            node.source = replace(source.source)
        self.output.stmts.append(node)
        return node

    def emit_index(self, expression: IndexExpr) -> ir.SSAValue:
        """Emit the integer operations that compute an index expression."""
        if (value := expression.constant) is not None:
            return self.push(py.Constant(value)).results[0]
        total = None
        for symbol, coefficient in expression.terms:
            term = self.emitted_symbol(symbol)
            if coefficient != 1:
                constant = self.push(py.Constant(coefficient)).results[0]
                term = self.integer(py.Mult, term, constant)
            total = term if total is None else self.integer(py.Add, total, term)
        assert total is not None
        if expression.offset:
            constant = self.push(py.Constant(expression.offset)).results[0]
            total = self.integer(py.Add, total, constant)
        return total

    def emitted_symbol(self, symbol: Sym) -> ir.SSAValue:
        """Return the emitted integer of a source index symbol.

        An `Iter` symbol maps to the emitted loop index.
        """
        if isinstance(symbol, Iter):
            source: ir.SSAValue = symbol.stmt.regions[0].blocks[0].args[0]
        else:
            source = symbol
        value = self.get(source)
        if not isinstance(value, ir.SSAValue):
            raise ir.ValidationError(
                self.statement, "An index symbol has no emitted integer value."
            )
        return value

    def integer(
        self,
        op: type[py.Add] | type[py.Sub] | type[py.Mult] | type[py.FloorDiv],
        left: ir.SSAValue,
        right: ir.SSAValue,
    ) -> ir.SSAValue:
        """Emit one integer operation and give its result the type `int`."""
        node = self.push(op(left, right))
        node.results[0].type = types.Int
        return node.results[0]

    def free_local_allocations(self) -> None:
        """Free each local allocation that the region still holds at its end."""
        for location in self.local_roots:
            if (value := self.latest.pop(location.root, None)) is not None:
                free = stmts.Free if isinstance(location, Qubit) else stmts.FreeRegister
                self.push(free(value))


def body_of(region: ir.Region, node: ir.Statement, count: int) -> ir.Block:
    """Return the one block of the source region `region` of `node`.

    The emitter builds one output block for each region, so a region with several
    blocks has no wire form. The block must take `count` arguments, which are the
    values that `node` passes into the region.
    """
    if len(region.blocks) != 1:
        raise ir.ValidationError(
            node, "Wire emission requires single-block structured regions."
        )
    block = region.blocks[0]
    if len(block.args) != count:
        raise ir.ValidationError(
            node, "Region arguments must match the supplied inputs."
        )
    return block


@dataclass
class EmitWire(EmitABC[WireFrame, Value]):
    """Translate source operations with method tables and explicit per-region wire state."""

    keys = ("emit.squin_wire",)
    void = None
    source: ir.Method
    converted: Mapping[ir.Method, ir.Method]
    """Hold the wire method of each user callee, which `SquinToWire` converts first."""
    wire_dialects: tuple[ir.Dialect, ...] = ()
    """Hold the dialects of the wire statements that other dialects emit, such as Gemini."""
    result: ir.Method | None = field(default=None, init=False)
    """Hold the emitted wire method, which the function handler sets at its end."""
    indices: Indices = field(init=False)
    """Hold the index expression of each source integer, whose symbols are source values."""
    lengths: dict[Sym, IndexExpr] = field(init=False)
    """Hold the constant length that each source `len` result reads."""

    def initialize_frame(
        self, node: ir.Statement, *, has_parent_access: bool = False
    ) -> WireFrame:
        """Create a region frame whose source values can access its enclosing frame."""
        return WireFrame(node, has_parent_access=has_parent_access)

    def reset(self) -> None:
        """Reset Kirin's callable queue and the result of this emission."""
        self.callables = EmitTable(prefix="")
        self.callable_to_emit = WorkList()
        self.result = None
        self.indices = Indices(self.dialects)
        self.lengths = {}

    def index(self, value: ir.SSAValue) -> IndexExpr:
        """Return the index expression of the source integer `value`.

        Each `len` result of a constant length reads as that constant.
        """
        return self.indices.of(value).substitute(self.lengths)

    def emit_method(self) -> ir.Method:
        """Emit one source method using the wire methods of its callees.

        Kirin's `run` evaluates `source.code`, which dispatches to the function
        handler in `functions.py`. That handler sets `result`.
        """
        self.run(self.source)
        assert self.result is not None
        return self.result

    def classical_value(self, frame: WireFrame, value: Value) -> ir.SSAValue:
        """Return the emitted classical value of a meaning.

        A tuple of meanings becomes an emitted tuple.
        """
        if isinstance(value, ir.SSAValue):
            return value
        if isinstance(value, WrapperSelf):
            raise ir.ValidationError(
                frame.statement, "A library wrapper cannot use its own function object."
            )
        if value is None:
            raise ir.ValidationError(
                frame.statement, "A statement without a result has no value."
            )
        if isinstance(value, tuple):
            return frame.push(
                py.tuple.New(tuple(self.classical_value(frame, x) for x in value))
            ).results[0]
        raise ir.ValidationError(
            frame.statement, "A classical operation cannot consume a quantum reference."
        )

    def acquire(self, frame: WireFrame, location: Location) -> ir.SSAValue:
        """Return the wire value of a location for an operation that consumes it.

        A whole allocation leaves `latest` until `restore`. An element emits a `Borrow`,
        and a slice with step 1 emits a `TakeSlice`. `restore` emits the matching
        `Release` or `PutSlice`.
        """
        value = frame.latest.get(location.root)
        if value is None:
            raise ir.ValidationError(
                frame.statement, "An operation cannot use one qubit or register twice."
            )
        match location:
            case Element(root, index):
                node = frame.push(stmts.Borrow(value, frame.emit_index(index)))
                frame.latest[root] = node.results[0]
                return node.results[1]
            case View(root, span, ()) if span.step == 1:
                start = frame.emit_index(span.start)
                size = self.length_value(frame, location)
                # A tail slice of runtime length reads the register with `Length`,
                # which continues the register.
                node = frame.push(stmts.TakeSlice(frame.latest[root], start, size))
                frame.latest[root] = node.register_out
                return node.slice_register
            case View():
                raise ir.ValidationError(
                    frame.statement,
                    "A whole-register operation requires a whole allocation.",
                )
            case Qubit(root) | Register(root):
                del frame.latest[root]
                return value

    def restore(self, frame: WireFrame, location: Location, value: ir.SSAValue) -> None:
        """Record the next value of a location after the operation that consumed it."""
        register = frame.latest.get(location.root)
        match location:
            case Element(index=index):
                assert register is not None
                at = frame.emit_index(index)
                value = frame.push(stmts.Release(register, at, value)).register_out
            case View(span=span):
                assert register is not None
                at = frame.emit_index(span.start)
                value = frame.push(stmts.PutSlice(register, at, value)).register_out
        frame.latest[location.root] = value

    def operate(
        self,
        frame: WireFrame,
        locations: Sequence[Location],
        build: Callable[[tuple[ir.SSAValue, ...]], ir.Statement],
    ) -> ir.Statement:
        """Emit the statement that `build` makes on the wires of `locations`.

        The statement must carry a `Threads` trait, and each location continues with
        its result. A dialect that adds statements to wire programs calls this from
        its method table under the key `emit.squin_wire`.
        """
        inputs = tuple(self.acquire(frame, location) for location in locations)
        made = frame.push(build(inputs))
        self.check_dialect(made)
        continued = dict(made.get_present_trait(Threads).threads(made))
        for location, wire in zip(locations, inputs, strict=True):
            if wire not in continued:
                raise ir.ValidationError(
                    made,
                    f"The Threads trait of '{made.name}' must continue each input.",
                )
            self.restore(frame, location, continued[wire])
        return made

    def check_dialect(self, made: ir.Statement) -> None:
        """Raise a conversion error if the wire method cannot hold `made`.

        A wire statement of another dialect needs its dialect in `wire_dialects`,
        so that the dialect group of the wire method holds it.
        """
        if made.dialect in WIRE_DIALECTS or made.dialect in self.wire_dialects:
            return
        name = "?" if made.dialect is None else made.dialect.name
        raise ir.ValidationError(
            made,
            f"The wire statement '{made.name}' belongs to the dialect '{name}'."
            " Pass that dialect to SquinToWire as one of its wire_dialects.",
        )

    def qubits_of(
        self, frame: WireFrame, value: ir.SSAValue, at: ir.Statement
    ) -> tuple[Single, ...]:
        """Return the location of each qubit that the source value `value` names.

        A qubit gives its own location. A list, a register or a slice of known
        length gives the location of each item in order. The function raises a
        conversion error for any other value.
        """
        meaning = frame.get(value)
        if isinstance(meaning, (Qubit, Element)):
            return (meaning,)
        items = known_items(meaning, at)
        if items is None:
            raise ir.ValidationError(
                at, f"'{at.name}' needs qubits whose places are all known."
            )
        return singles(items, at)

    def new_qubit(self, frame: WireFrame, wire: ir.SSAValue) -> Qubit:
        """Record the new wire `wire` as a standalone qubit of the current region.

        The region frees the qubit at its end, like a qubit of `qubit.new`.
        """
        if isinstance(wire.owner, ir.Statement):
            self.check_dialect(wire.owner)
        qubit = Qubit(wire)
        frame.own(qubit)
        return qubit

    def length_value(self, frame: WireFrame, value: Value) -> ir.SSAValue:
        """Return the length of a source container as an emitted integer.

        A constant or slice length becomes an index expression. Other register
        lengths emit `Length`, which reads the current register.
        A tail slice such as `qs[2:]` has the register length minus its start, or zero.
        """
        if isinstance(value, tuple):
            return frame.emit_index(IndexExpr(len(value)))
        match value:
            case View(length=length) if length is not None:
                return frame.emit_index(length)
            case View(root, Slice(start, 1, None), ()):
                qubits = self.register_length(frame, root)
                rest = frame.integer(py.Sub, qubits, frame.emit_index(start))
                # Python gives an empty tail past the end, and `(x + |x|) // 2` is
                # `max(0, x)`, which the dialects of wire methods can express.
                size = frame.push(py.builtin.Abs(rest)).result
                size.type = types.Int
                total = frame.integer(py.Add, rest, size)
                two = frame.push(py.Constant(2)).result
                return frame.integer(py.FloorDiv, total, two)
            case View() | Element() | Qubit():
                raise ir.ValidationError(
                    frame.statement, "The register view requires a known length."
                )
            case Register(length=length) if (
                length is not None and length.constant is not None
            ):
                return frame.emit_index(length)
            case Register(root, _, ()):
                return self.register_length(frame, root)
            case Register(root, _, row_shape):
                # `Length` counts qubits, and each row holds `row_width` of them.
                qubits = self.register_length(frame, root)
                width = frame.push(
                    py.Constant(row_width(row_shape, frame.statement))
                ).results[0]
                return frame.integer(py.FloorDiv, qubits, width)
        return frame.push(Len(self.classical_value(frame, value))).results[0]

    def register_length(self, frame: WireFrame, root: ir.SSAValue) -> ir.SSAValue:
        """Emit `Length` on the latest value of `root` and return the qubit count."""
        node = frame.push(stmts.Length(frame.latest[root]))
        frame.latest[root] = node.results[0]
        return node.results[1]

    def eval_fallback(self, frame: WireFrame, node: ir.Statement) -> tuple[Value, ...]:
        """Copy a classical operation with mapped operands.

        The quantum operations of each dialect have their own method table, such as
        the tables in `gates.py`. A statement on qubits without one has no wire form,
        and neither has a statement with regions other than a function, a loop or a
        branch.
        """
        if node.regions:
            raise ir.ValidationError(
                node, "Wire emission requires function, loop or branch regions."
            )
        values = frame.get_values(node.args)
        if any(contains_location(value) for value in values) or any(
            holds_qubits(result.type) for result in node.results
        ):
            raise ir.ValidationError(
                node,
                f"The statement '{node.name}' has no wire form for qubit references.",
            )
        made = node.from_stmt(
            node, args=tuple(self.classical_value(frame, value) for value in values)
        )
        frame.push(made)
        return tuple(made.results)
