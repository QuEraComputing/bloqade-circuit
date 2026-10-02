"""This module holds the emitter that builds jeff IR from squin kernels."""

import math
from typing import TypeVar, TypeAlias
from dataclasses import field, dataclass
from collections.abc import Mapping, Sequence

from kirin import ir, types, interp
from kirin.emit import EmitABC, EmitFrame
from kirin.dialects import func, ilist, ssacfg
from kirin.emit.abc import EmitTable
from kirin.worklist import WorkList

from bloqade.types import QubitType, MeasurementResultType
from bloqade.jeff.forms import EMIT_KEY, GateForm
from bloqade.jeff.types import (
    WireType,
    QuregType,
    IntArrayType,
    FloatArrayType,
    qureg,
    is_bit,
    is_subtype,
)
from bloqade.jeff.dialects import stmts, kernel as jeff_kernel
from bloqade.analysis.reference import (
    Ref,
    Root,
    Slot,
    Whole,
    Register,
    Untracked,
    positions,
)
from bloqade.jeff.dialects.stmts.call import declared_outputs
from bloqade.squin.analysis.reference import QubitReferenceAnalysis

KEY = EMIT_KEY

Value: TypeAlias = "ir.SSAValue | tuple[Value, ...] | None"
"""A jeff value, a literal tuple of values, or None for a value that a root names."""

_S = TypeVar("_S", bound=ir.Statement)


def jeff_kind(kind: types.TypeAttribute) -> types.TypeAttribute:
    """Return the jeff type of a value of the squin type `kind`."""
    if isinstance(kind, types.Literal):
        match kind.data:
            case bool():
                return types.Bool
            case int():
                return types.Int
            case float():
                return types.Float
            case ilist.IList(data=list(items)) if any(
                isinstance(item, float) for item in items
            ):
                return FloatArrayType
            case ilist.IList():
                return IntArrayType
    if kind.is_subseteq(QubitType):
        return WireType
    if kind.is_subseteq(MeasurementResultType):
        return types.Bool
    if kind.is_subseteq(ilist.IListType[QubitType, types.Any]):
        length = kind.vars[1] if isinstance(kind, types.Generic) else None
        return qureg(length.data if isinstance(length, types.Literal) else None)
    if kind.is_subseteq(ilist.IListType[types.Float, types.Any]):
        return FloatArrayType
    if kind.is_subseteq(ilist.IListType):
        return IntArrayType
    return kind


def elements(kind: types.TypeAttribute) -> types.TypeAttribute:
    """Return the element type of the list type `kind`, or `Any`."""
    if isinstance(kind, types.Generic) and kind.is_subseteq(ilist.IListType):
        return kind.vars[0]
    return types.Any


def bitwidth(elements: types.TypeAttribute) -> int:
    """Return the jeff bitwidth of an integer array with the element type `elements`.

    A measurement result or a boolean is one bit, any other integer is 32 bits.
    """
    if elements.is_subseteq(MeasurementResultType) or elements.is_subseteq(types.Bool):
        return 1
    return 32


@dataclass
class Frame(EmitFrame[Value]):
    """Hold the jeff block under construction and the current wire of each root."""

    body: ir.Block = field(default_factory=ir.Block, kw_only=True)
    """The jeff block under construction."""
    wires: dict[Root, ir.SSAValue] = field(default_factory=dict, kw_only=True)
    """The current wire of each root."""

    def push(self, stmt: _S) -> _S:
        """Append a jeff statement to the block and return it.

        An integer operation on bits gives a bit, which the statement types `Bool`.
        """
        if isinstance(stmt, (stmts.IntUnary, stmts.IntBinary)) and is_bit(stmt.args[0]):
            stmt.results[0].type = types.Bool
        self.body.stmts.append(stmt)
        return stmt

    def value(self, value: ir.SSAValue) -> Value:
        """Return the jeff value of `value`, or None if a root names `value`.

        A region reads the values of its parent frame directly, and
        `isolate_regions` later makes them inputs of the region.
        """
        if value in self.entries:
            return self.entries[value]
        if not isinstance(self.parent, Frame):
            raise interp.InterpreterError(f"{value} has no jeff value")
        return self.parent.value(value)

    def values(self, values: Sequence[ir.SSAValue]) -> tuple[Value, ...]:
        """Return the jeff value of each squin value in `values`."""
        return tuple(self.value(v) for v in values)

    def scalar(self, value: ir.SSAValue) -> ir.SSAValue:
        """Return the jeff value of the classical squin value `value`."""
        jeff = self.value(value)
        if not isinstance(jeff, ir.SSAValue):
            raise interp.InterpreterError(f"{value} has no jeff value")
        return jeff

    def wire(self, root: Root) -> ir.SSAValue:
        """Return the current wire of `root`, which may come from a parent frame."""
        if root in self.wires:
            return self.wires[root]
        if not isinstance(self.parent, Frame):
            raise interp.InterpreterError(f"{root} has no wire")
        return self.parent.wire(root)

    def outer(self, root: Root) -> bool:
        """Return True if a parent frame holds a wire of `root`."""
        frame = self.parent
        while isinstance(frame, Frame):
            if root in frame.wires:
                return True
            frame = frame.parent
        return False


@dataclass(frozen=True)
class Layout:
    """How a squin kernel maps to a jeff function.

    The jeff function hands the wire of each qubit parameter back as its first
    outputs, then returns the kept return values.
    """

    qubits: tuple[ir.BlockArgument, ...]
    """The parameters that carry a qubit or a register, in order."""
    kept: tuple[int, ...]
    """The return positions that are not a qubit parameter handed back."""
    kinds: tuple[types.TypeAttribute, ...]
    """The declared squin type of each return position."""


@dataclass
class Linearize(EmitABC[Frame, Value]):
    """Build a jeff method for each squin kernel by threading one wire per root."""

    keys = (KEY,)
    void = None
    dialects: ir.DialectGroup
    refs: Mapping[ir.SSAValue, Ref]
    """The reference of each value of each kernel, in the kernel's terms."""
    analysis: QubitReferenceAnalysis
    """The reference analysis that `refs` came from."""
    functions: dict[ir.Statement, ir.Method] = field(default_factory=dict, init=False)
    """The jeff method of each kernel copy, keyed by the code of the copy."""
    layouts: dict[ir.Statement, "Layout"] = field(default_factory=dict, init=False)
    """The layout of each kernel copy, keyed by the code of the copy."""

    def initialize_frame(
        self, node: ir.Statement, *, has_parent_access: bool = False
    ) -> Frame:
        """Create the frame of the body of a kernel copy under conversion."""
        return Frame(node, has_parent_access=has_parent_access)

    def reset(self) -> None:
        """Clear the state of the previous run."""
        self.callables = EmitTable(prefix="")
        self.callable_to_emit = WorkList()
        self.functions = {}
        self.layouts = {}

    def layout(self, code: func.Function) -> "Layout":
        """Return how the kernel copy `code` maps to a jeff function, memoized."""
        if code not in self.layouts:
            params = code.body.blocks[0].args[1:]
            qubits = tuple(p for p in params if not isinstance(self.refs[p], Untracked))
            returned = code.body.blocks[0].last_stmt
            if not isinstance(returned, func.Return):
                raise interp.InterpreterError(
                    f"{code.sym_name} does not end in a return"
                )
            result = self.refs[returned.value]
            kinds = declared_outputs(code.signature.output)
            refs = positions(result, len(kinds))
            kept = tuple(
                p
                for p, ref in enumerate(refs)
                if not (isinstance(ref, (Whole, Register)) and ref.root in qubits)
            )
            self.layouts[code] = Layout(qubits, kept, kinds)
        return self.layouts[code]

    def declare(self, code: func.Function) -> ir.Method:
        """Return the jeff method of the kernel copy `code`, made on first request.

        The method has its signature and an empty body. The outputs are the wires
        of the qubit parameters, then the kept return values.
        """
        if code in self.functions:
            return self.functions[code]
        params = code.body.blocks[0].args[1:]
        layout = self.layout(code)
        outputs = [jeff_kind(p.type) for p in layout.qubits]
        outputs += [jeff_kind(layout.kinds[p]) for p in layout.kept]
        match outputs:
            case []:
                output = types.NoneType
            case [only]:
                output = only
            case _:
                output = types.Generic(tuple, *outputs)
        inputs = [jeff_kind(p.type) for p in params]
        block = ir.Block()
        block.args.append_from(
            types.MethodType[inputs, output], f"{code.sym_name}_self"
        )
        for param, kind in zip(params, inputs, strict=True):
            block.args.append_from(kind, param.name)
        made = func.Function(
            sym_name=code.sym_name,
            slots=tuple(p.name or "" for p in params),
            body=ir.Region(block),
            signature=func.Signature(inputs=tuple(inputs), output=output),
        )
        method = ir.Method(dialects=jeff_kernel, code=made, sym_name=code.sym_name)
        self.functions[code] = method
        return method

    def take(self, frame: Frame, ref: Ref) -> ir.SSAValue:
        """Return the wire of `ref`, and extract it from its register for a slot."""
        match ref:
            case Whole(root) | Register(root):
                return frame.wire(root)
            case Slot(root, index):
                at = self.index(frame, index)
                extract = frame.push(stmts.Extract(frame.wire(root), at))
                frame.wires[root] = extract.result_reg
                return extract.wire
        raise interp.InterpreterError(f"{ref} names no wire")

    def give(self, frame: Frame, ref: Ref, wire: ir.SSAValue) -> None:
        """Make `wire` the current wire of `ref`, and insert it back for a slot."""
        match ref:
            case Whole(root) | Register(root):
                frame.wires[root] = wire
            case Slot(root, index):
                at = self.index(frame, index)
                insert = stmts.Insert(frame.wire(root), at, wire)
                frame.wires[root] = frame.push(insert).result

    def index(self, frame: Frame, index: int | ir.SSAValue) -> ir.SSAValue:
        """Return the jeff index of a slot at `index`.

        The validation refuses a negative constant index, which only a register
        of unknown length keeps.
        """
        if isinstance(index, ir.SSAValue):
            return frame.scalar(index)
        if index < 0:
            raise interp.InterpreterError(f"a negative index {index}")
        return frame.push(stmts.ConstInt(value=index)).result

    def qubits(self, value: ir.SSAValue) -> Sequence[Ref]:
        """Return the references of the qubits that `value` holds."""
        items = self.analysis.items(self.refs[value])
        if items is None:
            raise interp.InterpreterError(f"{value} holds no qubit that a wire carries")
        return items

    def gate(
        self,
        frame: Frame,
        form: GateForm,
        operands: Sequence[ir.SSAValue],
        angles: Sequence[ir.SSAValue],
        adjoint: bool,
    ) -> None:
        """Emit the gate `form` on each group of qubits of `operands`.

        Squin lists the controls first, and a jeff gate takes the targets first.
        """
        for group in zip(*(self.qubits(value) for value in operands), strict=True):
            refs = (*group[form.controls :], *group[: form.controls])
            wires = tuple(self.take(frame, ref) for ref in refs)
            targets = len(refs) - form.controls
            gate = stmts.Gate(
                wires[:targets],
                wires[targets:],
                tuple(angles),
                gate_name=form.name,
                adjoint=adjoint,
            )
            frame.push(gate)
            for ref, wire in zip(refs, gate.results, strict=True):
                self.give(frame, ref, wire)

    def measure(self, frame: Frame, value: ir.SSAValue) -> ir.SSAValue:
        """Measure each qubit of `value` and keep it.

        The result is the bit of one qubit, or a bit array for a list.
        """
        bits: list[ir.SSAValue] = []
        for ref in self.qubits(value):
            measured = frame.push(stmts.MeasureNd(self.take(frame, ref)))
            self.give(frame, ref, measured.result_wire)
            bits.append(measured.bit)
        if isinstance(self.refs[value], (Whole, Slot)):
            return bits[0]
        return frame.push(stmts.IntArrayCreate(tuple(bits), bitwidth=1)).result

    def reset_qubits(self, frame: Frame, value: ir.SSAValue) -> None:
        """Reset each qubit of `value`."""
        for ref in self.qubits(value):
            wire = self.take(frame, ref)
            self.give(frame, ref, frame.push(stmts.Reset(wire)).result)

    def negate(self, frame: Frame, value: ir.SSAValue) -> ir.SSAValue:
        """Return the negation of the bit `value`, or of each bit of the bit array."""
        bits = frame.scalar(value)
        if not value.type.is_subseteq(ilist.IListType):
            return frame.push(stmts.IntNot(bits)).result
        size = value.type.vars[1] if isinstance(value.type, types.Generic) else None
        if not isinstance(size, types.Literal):
            raise interp.InterpreterError(f"{value} is a bit array of unknown length")
        negated: list[ir.SSAValue] = []
        for position in range(size.data):
            at = frame.push(stmts.ConstInt(value=position)).result
            bit = frame.push(stmts.IntArrayGet(bits, at, bitwidth=1)).result
            negated.append(frame.push(stmts.IntNot(bit)).result)
        return frame.push(stmts.IntArrayCreate(tuple(negated), bitwidth=1)).result

    def leave(self, inner: Frame, outs: Sequence[ir.SSAValue]) -> ir.Region:
        """End the block of `inner` with a yield of `outs` and return it as a region.

        The wires of the roots that the region allocates are freed.
        """
        self.free(inner, [root for root in inner.wires if inner.outer(root)])
        inner.push(stmts.Yield(*outs))
        return ir.Region(inner.body)

    def fitted(
        self, frame: Frame, value: ir.SSAValue, kind: types.TypeAttribute
    ) -> ir.SSAValue:
        """Return the jeff `value` as the squin type `kind` expects it.

        Squin joins a bit and an integer to an integer. Jeff has no conversion,
        so a bit in an integer position becomes `int_select(bit, 1, 0)`.
        """
        if is_bit(value) and jeff_kind(kind) == types.Int:
            one = frame.push(stmts.ConstInt(value=1)).result
            zero = frame.push(stmts.ConstInt(value=0)).result
            return frame.push(stmts.IntSelect(value, one, zero)).result
        return value

    def free(self, frame: Frame, kept: Sequence[Root]) -> None:
        """Release the wire of each root of `frame` that `kept` does not name."""
        for root, wire in frame.wires.items():
            if root in kept:
                continue
            if is_subtype(wire.type, QuregType):
                frame.push(stmts.RegFree(wire))
            else:
                frame.push(stmts.Free(wire))

    def radians(self, frame: Frame, turns: ir.SSAValue) -> ir.SSAValue:
        """Return the angle in radians of the squin gate statement angle `turns`."""
        full = frame.push(stmts.ConstFloat(value=2 * math.pi)).result
        return frame.push(stmts.FloatMul(frame.scalar(turns), full)).result


@ssacfg.dialect.register(key=KEY)
class _SsaCfg(ssacfg.Concrete):
    """Run the statements of an SSA control-flow region with kirin's concrete rule."""
