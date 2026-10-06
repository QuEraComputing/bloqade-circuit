"""This module holds the pass that turns jeff wires and registers into squin qubits."""

import math
from dataclasses import field, dataclass
from collections.abc import Mapping

from kirin import ir, types
from kirin.passes import Pass
from kirin.rewrite import Walk, Chain
from kirin.dialects import py, scf, func, ilist
from kirin.dialects.py import len as py_len, slice as py_slice
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.qubit import stmts as qubit_stmts
from bloqade.types import QubitType
from bloqade.jeff.gates import canonical
from bloqade.jeff.types import WireType, QuregType, is_subtype, qureg_length
from bloqade.squin.gate import stmts as gate_stmts
from bloqade.jeff.dialects import stmts
from bloqade.analysis.reference import Ref, Slot, Whole, Register
from bloqade.jeff.analysis.validation.to_squin.gates import (
    SINGLE,
    ROTATION,
    CONTROLLED,
    NON_HERMITIAN,
    gate_supported,
)


@dataclass(frozen=True)
class Conversion:
    """The kernel copy of a jeff function with what its wire analysis found."""

    kernel: ir.Method
    entries: Mapping[ir.SSAValue, Ref]
    """The reference of each wire value of the kernel."""


@dataclass
class Delinearize(Pass):
    """A pass that rewrites the jeff quantum statements of a method for squin."""

    conversions: Mapping[ir.Method, Conversion] = field(kw_only=True)
    """The conversion of each jeff function, the method's own among them."""

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        """Rewrite `mt` in place and retype its parameters for squin.

        Type inference retypes every other value from the parameters.
        """
        own = next(c for c in self.conversions.values() if c.kernel is mt)
        # `_Calls` looks up the reference of each call input in `own.entries`.
        # The other rules replace jeff values by new squin values, which have
        # no entry. So `_Calls` rewrites every call before the other rules run.
        result = Walk(_Calls(self.conversions, own.entries)).rewrite(mt.code)
        rules = Chain(
            _Return(),
            _Qubits(),
            _Gates(),
            _Registers(own.entries),
        )
        result = Walk(rules).rewrite(mt.code).join(result)
        # A jeff loop threads every live wire through its state. Once the gates
        # act in place, such a wire is a loop variable yielded unchanged.
        result = Walk(scf.trim.UnusedYield()).rewrite(mt.code).join(result)
        for arg in mt.args:
            arg.type = _squin_type(arg.type)
        # Type inference computes the output. A declared output can disagree
        # with a folded constant tuple, which kirin types as a bare `tuple`.
        ir.HasSignature.set_signature(
            mt.code, func.Signature(inputs=tuple(mt.arg_types), output=types.Any)
        )
        return result


def _squin_type(kind: types.TypeAttribute) -> types.TypeAttribute:
    """Return `kind` with a wire read as a qubit and a register as a list of qubits."""
    if is_subtype(kind, WireType):
        return QubitType
    if is_subtype(kind, QuregType):
        length = qureg_length(kind)
        return ilist.IListType[
            QubitType, types.Any if length is None else types.Literal(length)
        ]
    return kind


def _wrap(ref: ir.SSAValue, before: ir.Statement) -> ir.SSAValue:
    """Return a one-element list of `ref`, which squin statements take."""
    (wrapped := ilist.New([ref])).insert_before(before)
    return wrapped.result


def _const(value: int | float, before: ir.Statement) -> ir.SSAValue:
    """Return a constant of `value`."""
    (constant := py.Constant(value)).insert_before(before)
    return constant.result


def _negate(value: ir.SSAValue, before: ir.Statement) -> ir.SSAValue:
    """Return the negated value."""
    (negated := py.unary.USub(value)).insert_before(before)
    return negated.result


def _replace(stmt: ir.Statement, *values: ir.SSAValue) -> RewriteResult:
    """Replace the results of `stmt` by `values` in order, then delete `stmt`."""
    for result, value in zip(stmt.results, values, strict=True):
        result.replace_by(value)
    stmt.delete()
    return RewriteResult(has_done_something=True)


class _Qubits(RewriteRule):
    """A rewrite rule that rewrites qubit allocation, freeing, reset and measurement."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Rewrite `node` if it allocates, frees, resets or measures a qubit."""
        match node:
            case stmts.Alloc():
                (qubit := qubit_stmts.New()).insert_before(node)
                return _replace(node, qubit.result)
            case (
                stmts.Free() | stmts.FreeZero() | stmts.RegFree() | stmts.RegFreeZero()
            ):
                node.delete()
                return RewriteResult(has_done_something=True)
            case stmts.Reset():
                qubit_stmts.Reset(_wrap(node.wire, node)).insert_before(node)
                return _replace(node, node.wire)
            case stmts.Measure() | stmts.MeasureNd():
                (measured := qubit_stmts.Measure(_wrap(node.wire, node))).insert_before(
                    node
                )
                index = _const(0, node)
                (bit := py.indexing.GetItem(measured.result, index)).insert_before(node)
                if isinstance(node, stmts.MeasureNd):
                    return _replace(node, node.wire, bit.result)
                return _replace(node, bit.result)
        return RewriteResult()


class _Gates(RewriteRule):
    """A rewrite rule that applies a jeff gate as squin gate statements."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Apply `node` once per unit of its power and map each output to its input."""
        if not isinstance(node, stmts.Gate):
            return RewriteResult()
        shape = canonical(node)
        if not gate_supported(shape):
            return RewriteResult()
        name, adjoint = shape.name, shape.adjoint
        for _ in range(shape.power):
            targets = [_wrap(w, node) for w in shape.targets]
            controls = [_wrap(w, node) for w in shape.controls]
            match controls, name:
                case [control], _:
                    CONTROLLED[name](control, targets[0]).insert_before(node)
                case [first, second], _:
                    gate_stmts.CCZ(first, second, targets[0]).insert_before(node)
                case [], "u":
                    theta, phi, lam = (_turns(p, node) for p in shape.params)
                    if adjoint:
                        theta, phi, lam = (_negate(a, node) for a in (theta, lam, phi))
                    gate_stmts.U3(theta, phi, lam, targets[0]).insert_before(node)
                case [], "swap":
                    gate_stmts.Swap(targets[0], targets[1]).insert_before(node)
                case [], _ if name in SINGLE:
                    SINGLE[name](targets[0]).insert_before(node)
                case [], _ if name in NON_HERMITIAN:
                    NON_HERMITIAN[name](targets[0], adjoint=adjoint).insert_before(node)
                case [], _ if name in ROTATION:
                    angle = _turns(shape.params[0], node)
                    if adjoint:
                        angle = _negate(angle, node)
                    ROTATION[name](angle, targets[0]).insert_before(node)
        return _replace(node, *node.targets, *node.controls)


def _turns(radians: ir.SSAValue, before: ir.Statement) -> ir.SSAValue:
    """Convert an angle from radians to squin's turns.

    The conversion multiplies, because jeff has no float division and a squin
    kernel that goes back to jeff must stay expressible.
    """
    turn = _const(1 / (2 * math.pi), before)
    (turns := py.binop.Mult(radians, turn)).insert_before(before)
    return turns.result


@dataclass
class _Registers(RewriteRule):
    """A rewrite rule that rewrites register statements as list operations.

    An insert that returns a wire to the slot that it came from keeps the list.
    """

    entries: Mapping[ir.SSAValue, Ref]

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Rewrite `node` if it is a register statement."""
        match node:
            case stmts.RegAlloc():
                (
                    invoke := func.Invoke((node.size,), callee=squin.qalloc)
                ).insert_before(node)
                return _replace(node, invoke.result)
            case stmts.RegCreate():
                (created := ilist.New(list(node.wires))).insert_before(node)
                return _replace(node, created.result)
            case stmts.Extract():
                (get := py.indexing.GetItem(node.reg, node.index)).insert_before(node)
                return _replace(node, node.reg, get.result)
            case stmts.Insert():
                if isinstance(self.entries.get(node.result), Register):
                    return _replace(node, node.reg)
                one = _const(1, node)
                (stop := py.binop.Add(node.index, one)).insert_before(node)
                element = _wrap(node.wire, node)
                spliced = _splice(node.reg, node.index, stop.result, element, node)
                return _replace(node, spliced)
            case stmts.ExtractSlice():
                (stop := py.binop.Add(node.start, node.length)).insert_before(node)
                one = _const(1, node)
                (sliced := py_slice.Slice(node.start, stop.result, one)).insert_before(
                    node
                )
                (part := py.indexing.GetItem(node.reg, sliced.result)).insert_before(
                    node
                )
                return _replace(node, node.reg, part.result)
            case stmts.InsertSlice():
                (length := py_len.Len(node.slice_reg)).insert_before(node)
                (stop := py.binop.Add(node.start, length.result)).insert_before(node)
                spliced = _splice(
                    node.reg, node.start, stop.result, node.slice_reg, node
                )
                return _replace(node, spliced)
            case stmts.RegSplit():
                (length := py_len.Len(node.reg)).insert_before(node)
                zero, one = _const(0, node), _const(1, node)
                (head := py_slice.Slice(zero, node.index, one)).insert_before(node)
                (front := py.indexing.GetItem(node.reg, head.result)).insert_before(
                    node
                )
                one = _const(1, node)
                tail = py_slice.Slice(node.index, length.result, one)
                tail.insert_before(node)
                (back := py.indexing.GetItem(node.reg, tail.result)).insert_before(node)
                return _replace(node, front.result, back.result)
            case stmts.RegJoin():
                (joined := py.binop.Add(node.first, node.second)).insert_before(node)
                return _replace(node, joined.result)
            case stmts.RegLength():
                (length := py_len.Len(node.reg)).insert_before(node)
                return _replace(node, node.reg, length.result)
        return RewriteResult()


def _splice(
    reg: ir.SSAValue,
    start: ir.SSAValue,
    stop: ir.SSAValue,
    middle: ir.SSAValue,
    before: ir.Statement,
) -> ir.SSAValue:
    """Return `reg` with `middle` in place of the slots from `start` to `stop`."""
    zero, one = _const(0, before), _const(1, before)
    (length := py_len.Len(reg)).insert_before(before)
    (head_slice := py_slice.Slice(zero, start, one)).insert_before(before)
    (head := py.indexing.GetItem(reg, head_slice.result)).insert_before(before)
    (tail_slice := py_slice.Slice(stop, length.result, one)).insert_before(before)
    (tail := py.indexing.GetItem(reg, tail_slice.result)).insert_before(before)
    (front := py.binop.Add(head.result, middle)).insert_before(before)
    (whole := py.binop.Add(front.result, tail.result)).insert_before(before)
    return whole.result


class _Return(RewriteRule):
    """A rewrite rule that returns every output, as none, one value or a tuple."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Rewrite `node` if it is a jeff return."""
        if not isinstance(node, stmts.Return):
            return RewriteResult()
        values = list(node.values)
        if not values:
            (none := func.ConstantNone()).insert_before(node)
            value = none.result
        elif len(values) == 1:
            value = values[0]
        else:
            (packed := py.tuple.New(tuple(values))).insert_before(node)
            value = packed.result
        node.replace_by(func.Return(value))
        return RewriteResult(has_done_something=True)


@dataclass
class _Calls(RewriteRule):
    """A rewrite rule that invokes the squin kernel of each jeff callee.

    A squin call changes its qubits in place. So an output that refers to the same
    wire or register as an input is that input. The call result supplies each other
    output.
    """

    conversions: Mapping[ir.Method, Conversion]
    entries: Mapping[ir.SSAValue, Ref]
    """The reference of each wire value of the caller."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Rewrite `node` if it is a jeff call."""
        if not isinstance(node, stmts.Call):
            return RewriteResult()
        kernel = self.conversions[node.callee].kernel
        (invoke := func.Invoke(tuple(node.inputs), callee=kernel)).insert_before(node)
        values: list[ir.SSAValue] = []
        for i, result in enumerate(node.results):
            if (same := self._input(node, result)) is not None:
                values.append(same)
            elif len(node.results) == 1:
                values.append(invoke.result)
            else:
                read = py.indexing.GetItem(invoke.result, _const(i, node))
                read.insert_before(node)
                values.append(read.result)
        return _replace(node, *values)

    def _input(self, node: stmts.Call, result: ir.SSAValue) -> ir.SSAValue | None:
        """Return the input of `node` that refers to the same state as `result`."""
        ref = self.entries.get(result)
        if not isinstance(ref, Whole | Register | Slot):
            return None
        return next((v for v in node.inputs if self.entries.get(v) == ref), None)
