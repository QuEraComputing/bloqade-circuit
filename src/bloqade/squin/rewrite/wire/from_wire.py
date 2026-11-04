"""Turn wire squin back into reference squin with the kirin rewrite rules of `FromWire`.

Every wire statement hands each wire on to a result. So a qubit keeps one
reference squin value along its whole chain of wires. The rule for each statement
replaces the results of the statement with its inputs. Once the rule for `Alloc`
replaces the first wire of a chain with a `qubit.new` result, every later
statement on the chain reads that qubit. The order of the rewrites therefore
makes no difference.

The rules for loops and branches run after the other rules. They remove the
carried wires from the initializers, the block arguments and the yields.

A borrowing call returns the wires of its qubit arguments after its ordinary
outputs. The call rule reads each returned wire as the argument that went in. The
signature rule turns each wire parameter back into a qubit parameter and drops the
returned wires from the return statement.
"""

from typing import Any
from dataclasses import field, dataclass
from collections.abc import Callable

from kirin import ir, types
from kirin.rewrite import Walk, Chain, DeadCodeElimination
from kirin.dialects import py, scf, func, ilist
from kirin.dialects.py import len as py_len, slice as py_slice
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.qubit import stmts as qubit_stmts, qalloc
from bloqade.types import QubitType, is_subtype
from bloqade.squin.wire import stmts
from bloqade.squin.wire.group import is_wire, reference_group
from bloqade.squin.wire.types import RegisterType, is_linear
from bloqade.squin.wire.errors import WireConversionError
from bloqade.squin.wire.traits import Threads, ReferenceForm
from bloqade.squin.wire.sources import source_of
from bloqade.squin.wire.ownership import KEY as OWNED, owns_inputs
from bloqade.squin.wire.signature import packed_type, output_types
from bloqade.squin.rewrite.wire.driver import CheckedFixpoint, put


def squin_type(kind: types.TypeAttribute) -> types.TypeAttribute:
    """Return the reference squin type of the wire squin type `kind`."""
    if is_subtype(kind, RegisterType):
        return ilist.IListType[QubitType, types.Any]
    if is_linear(kind):
        return QubitType
    if isinstance(kind, types.Generic) and is_subtype(kind, types.Tuple):
        return types.Generic(tuple, *(squin_type(member) for member in kind.vars))
    return kind


def _kept_outputs(
    signature: func.Signature, owned: bool = False
) -> tuple[types.TypeAttribute, ...]:
    """Return the ordinary output types of a wire function with `signature`.

    The wire function returns one wire for each linear parameter after them. A
    function without such wires returns its source result whole, which keeps the
    shape of a tuple of one item.
    """
    borrowed = 0 if owned else sum(is_linear(kind) for kind in signature.inputs)
    if not borrowed:
        none = is_subtype(signature.output, types.NoneType)
        return () if none else (squin_type(signature.output),)
    outputs = output_types(signature.output)
    return tuple(squin_type(kind) for kind in outputs[: len(outputs) - borrowed])


@dataclass
class FromWireStatements(RewriteRule):
    """Replace each wire statement outside a loop or branch with reference squin."""

    wire_dialects: tuple[ir.Dialect, ...] = ()
    """The dialects of the wire statements that other dialects add."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Rewrite `node` if it belongs to the wire dialect or a wire extension."""
        if node.dialect in self.wire_dialects and not node.has_trait(ReferenceForm):
            raise WireConversionError(
                f"The wire statement '{node.name}' has no ReferenceForm trait, so"
                " WireToSquin cannot rebuild it.",
                node,
            )
        if isinstance(node, stmts.Operation):
            self.operation(node)
        elif (form := node.get_trait(ReferenceForm)) is not None:
            self.extension(node, form)
        elif (rule := REFERENCE_RULES.get(type(node))) is not None:
            rule(node)
        else:
            return RewriteResult()
        node.delete()
        return RewriteResult(has_done_something=True)

    def extension(self, node: ir.Statement, form: ReferenceForm) -> None:
        """Insert the reference form of a wire statement that another dialect owns.

        `form` returns one value for each result that no `Threads` pair continues.
        Each continuing result reads as its operand.
        """
        threads = node.get_trait(Threads)
        continued = dict(
            (result, operand)
            for operand, result in ([] if threads is None else threads.threads(node))
        )
        fresh = [result for result in node.results if result not in continued]
        values = form.rebuild(node)
        if len(values) != len(fresh):
            raise WireConversionError(
                f"The ReferenceForm of '{node.name}' returned {len(values)} values"
                f" for {len(fresh)} results that no Threads pair continues.",
                node,
            )
        for result, value in zip(fresh, values, strict=True):
            result.replace_by(value)
        for result, operand in continued.items():
            result.replace_by(operand)

    def operation(self, node: stmts.Operation) -> None:
        """Insert the squin statement of the wire operation `node` before it.

        On a scalar operation, qubit field `j` of the squin statement gets the list
        of wire `j` of every group. So `Gate(kind=cx, wires=(c0, t0, c1, t1))`
        becomes `cx([c0, c1], [t0, t1])`. A scalar result, such as a measurement
        result, becomes item 0 of the list result of the squin statement. On a
        register operation, each register becomes the list of qubits that it holds,
        and each list result stays a list.
        """
        entry = source_of(node)
        scalar = not isinstance(node, stmts.RegisterOperation)
        if scalar:
            qubits = tuple(
                put(ilist.New(values=column, elem_type=QubitType), node).result
                for column in zip(*node.groups)
            )
        else:
            qubits = node.linear
        adjoint = (
            node.adjoint
            if isinstance(node, (stmts.Gate, stmts.RegisterGate))
            else False
        )
        made = put(entry.build(qubits, node.parameters, adjoint), node)
        for result, value in zip(
            node.classical, entry.result_values(made), strict=True
        ):
            if scalar:
                zero = put(py.Constant(0), node)
                item = put(py.GetItem(value, zero.result), node)
                item.result.type = result.type
                value = item.result
            result.replace_by(value)
        for output, value in zip(node.outputs, node.linear, strict=True):
            output.replace_by(value)


def from_alloc(node: stmts.Alloc) -> None:
    """Read the wire of an allocation as a new qubit."""
    node.result.replace_by(put(qubit_stmts.New(), node).result)


def from_alloc_register(node: stmts.AllocRegister) -> None:
    """Read the register of an allocation as a call of `qalloc`."""
    call = put(func.Invoke((node.size,), callee=qalloc), node)
    call.result.type = qalloc.return_type
    node.result.replace_by(call.result)


def from_borrow(node: stmts.Borrow | stmts.Take) -> None:
    """Read the borrowed wire as the qubit at its index."""
    item = put(py.GetItem(node.register, node.index), node)
    item.result.type = QubitType
    node.wire.replace_by(item.result)
    node.register_out.replace_by(node.register)


def from_put(node: stmts.Put) -> None:
    """Read the filled register as the list with the qubit at its index."""
    one = put(py.Constant(1), node).result
    stop = put(py.Add(node.index, one), node).result
    middle = put(ilist.New((node.wire,), elem_type=QubitType), node).result
    node.register_out.replace_by(_splice(node.register, node.index, stop, middle, node))


def from_pack(node: stmts.PackRegister) -> None:
    """Read the packed register as the list of its qubits."""
    node.result.replace_by(put(ilist.New(node.wires, elem_type=QubitType), node).result)


def from_join(node: stmts.JoinRegister) -> None:
    """Read the joined register as the concatenation of both lists."""
    node.result.replace_by(put(py.Add(node.first, node.second), node).result)


def from_split(node: stmts.SplitRegister) -> None:
    """Read both parts of the split register as slices of its list."""
    zero = put(py.Constant(0), node).result
    one = put(py.Constant(1), node).result
    length = put(py_len.Len(node.register), node).result
    head = put(py_slice.Slice(zero, node.index, one), node).result
    tail = put(py_slice.Slice(node.index, length, one), node).result
    node.before.replace_by(put(py.GetItem(node.register, head), node).result)
    node.after.replace_by(put(py.GetItem(node.register, tail), node).result)


def from_take_slice(node: stmts.TakeSlice) -> None:
    """Read the moved range as a slice of the register list."""
    stop = put(py.Add(node.start, node.length), node).result
    one = put(py.Constant(1), node).result
    part = put(py_slice.Slice(node.start, stop, one), node).result
    node.slice_register.replace_by(put(py.GetItem(node.register, part), node).result)
    node.register_out.replace_by(node.register)


def from_put_slice(node: stmts.PutSlice) -> None:
    """Read the filled register as the list with the slice in its range.

    If the slice returns to the range that it left, the register list holds the
    same qubit references as before.
    """
    if _restores(node):
        node.register_out.replace_by(node.register)
        return
    length = put(py_len.Len(node.slice_register), node).result
    stop = put(py.Add(node.start, length), node).result
    node.register_out.replace_by(
        _splice(node.register, node.start, stop, node.slice_register, node)
    )


def from_release(node: stmts.Release) -> None:
    """Read the register after a release as the register before it."""
    node.register_out.replace_by(node.register)


def from_length(node: stmts.Length) -> None:
    """Read the length of a register as the length of its list."""
    node.result.replace_by(put(py_len.Len(node.register), node).result)
    node.register_out.replace_by(node.register)


def from_free(node: stmts.Free | stmts.FreeRegister | stmts.DiscardRegister) -> None:
    """Drop a free, which has no reference squin form."""


REFERENCE_RULES: dict[type[ir.Statement], Callable[[Any], None]] = {
    stmts.Alloc: from_alloc,
    stmts.AllocRegister: from_alloc_register,
    stmts.Borrow: from_borrow,
    stmts.Take: from_borrow,
    stmts.Put: from_put,
    stmts.PackRegister: from_pack,
    stmts.JoinRegister: from_join,
    stmts.SplitRegister: from_split,
    stmts.TakeSlice: from_take_slice,
    stmts.PutSlice: from_put_slice,
    stmts.Release: from_release,
    stmts.Length: from_length,
    stmts.Free: from_free,
    stmts.FreeRegister: from_free,
    stmts.DiscardRegister: from_free,
}
"""Map each wire statement class to the rule that inserts its reference form.

Each rule inserts the reference statements before the wire statement and replaces
its results. `FromWireStatements` then deletes the wire statement.
"""


def _without(values: tuple[ir.SSAValue, ...], dropped: list[int]) -> list[ir.SSAValue]:
    """Return `values` without the positions in `dropped`."""
    return [v for k, v in enumerate(values) if k not in dropped]


def _strip_yield(block: ir.Block, dropped: list[int]) -> None:
    """Replace the yield of `block` with a yield that lacks the positions `dropped`."""
    old = block.last_stmt
    assert isinstance(old, scf.Yield)
    scf.Yield(*_without(old.values, dropped)).insert_before(old)
    old.delete()


class FromWireRegions(RewriteRule):
    """Remove the carried wires of each loop and branch.

    The rule waits until `FromWireStatements` has rewritten the bodies, so that
    every carried value is a qubit of the enclosing block.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Rewrite `node` if it is a loop or a branch with carried wires."""
        if isinstance(node, scf.For):
            return self.loop(node)
        if isinstance(node, scf.IfElse):
            return self.branch(node)
        return RewriteResult()

    def loop(self, node: scf.For) -> RewriteResult:
        """Read each carried qubit from its initializer and drop the carried wire."""
        block = node.body.blocks[0]
        dropped = [k for k, arg in enumerate(block.args[1:]) if is_linear(arg.type)]
        if not dropped:
            return RewriteResult()
        for k in dropped:
            block.args[k + 1].replace_by(node.initializers[k])
            node.results[k].replace_by(node.initializers[k])
        _strip_yield(block, dropped)
        for k in reversed(dropped):
            block.args[k + 1].delete()
        region = node.body
        region.detach()
        kept = _without(tuple(node.results), dropped)
        made = scf.For(node.iterable, region, *_without(node.initializers, dropped))
        made.insert_before(node)
        for old, new in zip(kept, made.results, strict=True):
            old.replace_by(new)
        node.delete()
        return RewriteResult(has_done_something=True)

    def branch(self, node: scf.IfElse) -> RewriteResult:
        """Replace each carried wire result with the qubit that the branch yields."""
        dropped = [k for k, r in enumerate(node.results) if is_linear(r.type)]
        if not dropped:
            return RewriteResult()
        then_yield = node.then_body.blocks[0].last_stmt
        assert isinstance(then_yield, scf.Yield)
        if any(is_linear(then_yield.values[k].type) for k in dropped):
            return RewriteResult()
        for k in dropped:
            node.results[k].replace_by(then_yield.values[k])
        for body in (node.then_body, node.else_body):
            _strip_yield(body.blocks[0], dropped)
        kept = _without(tuple(node.results), dropped)
        then_body, else_body = node.then_body, node.else_body
        then_body.detach()
        else_body.detach()
        made = scf.IfElse(node.cond, then_body, else_body)
        made.insert_before(node)
        for old, new in zip(kept, made.results, strict=True):
            old.replace_by(new)
        node.delete()
        return RewriteResult(has_done_something=True)


@dataclass
class FromWireCalls(RewriteRule):
    """Replace each call of a wire function with a call of its squin kernel.

    `convert` returns the squin kernel of a wire method. A returned wire of a
    borrowed argument becomes the argument itself.
    """

    convert: "FromWire"

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Rewrite `node` if it calls a wire squin method."""
        if not isinstance(node, func.Invoke) or not is_wire(node.callee):
            return RewriteResult()
        assert isinstance(node.callee.code, func.Function)
        signature = node.callee.code.signature
        owned = owns_inputs(node.callee)
        squin_kernel = self.convert.kernel_of(node.callee)
        call = put(func.Invoke(node.inputs, callee=squin_kernel), node)
        kept = _kept_outputs(signature, owned)
        call.result.type = packed_type(kept)
        borrowed = (
            []
            if owned
            else [a for a, k in zip(node.inputs, signature.inputs) if is_linear(k)]
        )
        total = len(kept) + len(borrowed)

        def output(k: int, before: ir.Statement) -> ir.SSAValue:
            if k >= len(kept):
                return borrowed[k - len(kept)]
            if len(kept) == 1:
                return call.result
            at = put(py.Constant(k), before)
            item = put(py.GetItem(call.result, at.result), before)
            item.result.type = kept[k]
            return item.result

        if total == 1:
            node.result.replace_by(output(0, node))
        elif total > 1:
            for use in list(node.result.uses):
                item = use.stmt
                assert isinstance(item, py.GetItem)
                index = item.index.owner
                assert isinstance(index, py.Constant)
                item.result.replace_by(output(index.value.unwrap(), item))
                item.delete()
        node.delete()
        return RewriteResult(has_done_something=True)


class FromWireSignature(RewriteRule):
    """Give a wire function the signature of its squin kernel.

    Each wire or register parameter becomes a qubit or a list of qubits. The return
    statement drops the wires that the function hands back.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Rewrite `node` if it is a function with linear parameters or outputs."""
        if not isinstance(node, func.Function):
            return RewriteResult()
        signature = node.signature
        outputs = output_types(signature.output)
        if not any(is_linear(k) for k in (*signature.inputs, *outputs)):
            return RewriteResult()
        owned = node.attributes.get(OWNED) == ir.PyAttr(True)
        kept = _kept_outputs(signature, owned)
        block = node.body.blocks[0]
        returned = block.last_stmt
        assert isinstance(returned, func.Return)
        # Without borrowed wires, the function returns its source result whole.
        if not owned and any(is_linear(kind) for kind in signature.inputs):
            if len(outputs) == 1:
                values = [returned.value]
            elif isinstance(made := returned.value.owner, py.tuple.New):
                values = list(made.args)
            else:
                values = []
            values = values[: len(kept)]
            if not values:
                value = put(func.ConstantNone(), returned).result
            elif len(values) == 1:
                value = values[0]
            else:
                value = put(py.tuple.New(tuple(values)), returned).result
            put(func.Return(value), returned)
            returned.delete()
        inputs = tuple(squin_type(k) for k in signature.inputs)
        for arg in block.args[1:]:
            arg.type = squin_type(arg.type)
        output = packed_type(kept)
        block.args[0].type = types.MethodType[list(inputs), output]
        node.signature = func.Signature(inputs=inputs, output=output)
        return RewriteResult(has_done_something=True)


@dataclass
class FromWire:
    """Convert wire squin methods into squin kernels, one copy per method."""

    wire_dialects: tuple[ir.Dialect, ...] = ()
    """The dialects of the wire statements that other dialects add.

    The squin kernels leave these dialects out of their dialect groups.
    """
    kernels: dict[ir.Method, ir.Method] = field(default_factory=dict)
    """Map each wire method to its squin kernel."""
    pending: list[ir.Method] = field(default_factory=list)
    """Hold the wire methods whose squin kernels still need the rewrite."""

    def kernel_of(self, method: ir.Method) -> ir.Method:
        """Return the squin kernel of the wire method `method`, made on first request.

        The kernel starts as a copy, and `convert` rewrites it later. So a call in
        a recursive kernel can name the kernel before its rewrite.
        """
        if method not in self.kernels:
            self.kernels[method] = method.similar(
                reference_group(method.dialects, self.wire_dialects)
            )
            self.pending.append(method)
        return self.kernels[method]

    def convert(self, method: ir.Method) -> ir.Method:
        """Return the squin kernel of `method` and of every wire method that it calls."""
        result = self.kernel_of(method)
        while self.pending:
            self.rewrite(self.kernels[self.pending.pop()])
        return result

    def rewrite(self, method: ir.Method) -> RewriteResult:
        """Run the statement rules, then the region and signature rules, then DCE."""
        statements = Walk(
            Chain(FromWireStatements(self.wire_dialects), FromWireCalls(self))
        )
        result = CheckedFixpoint(statements).rewrite(method.code)
        if owns_inputs(method):
            result = Walk(FromWireSignature()).rewrite(method.code).join(result)
            result = Walk(ReferenceTypes()).rewrite(method.code).join(result)
            method.code.attributes.pop(OWNED)
            return result
        regions = Walk(Chain(FromWireRegions(), FromWireSignature()))
        result = CheckedFixpoint(regions).rewrite(method.code).join(result)
        return (
            CheckedFixpoint(Walk(DeadCodeElimination()))
            .rewrite(method.code)
            .join(result)
        )


def _restores(node: stmts.PutSlice) -> bool:
    """Check whether `node` puts a slice back into the range that it came from.

    The `TakeSlice` rule has already turned the slice into `register[start:stop]`.
    """
    part = node.slice_register.owner
    if not isinstance(part, py.GetItem) or part.obj is not node.register:
        return False
    bounds = part.index.owner
    return isinstance(bounds, py_slice.Slice) and _same(bounds.start, node.start)


def _same(left: ir.SSAValue, right: ir.SSAValue) -> bool:
    """Check whether 2 integer values come from equal constants and arithmetic."""
    if left is right:
        return True
    a, b = left.owner, right.owner
    if isinstance(a, py.Constant) and isinstance(b, py.Constant):
        return a.value == b.value
    return (
        type(a) is type(b)
        and isinstance(a, (py.Add, py.Sub, py.Mult))
        and all(_same(x, y) for x, y in zip(a.args, b.args, strict=True))
    )


def _splice(
    reg: ir.SSAValue,
    start: ir.SSAValue,
    stop: ir.SSAValue,
    middle: ir.SSAValue,
    before: ir.Statement,
) -> ir.SSAValue:
    """Return `reg` with `middle` in place of the slots from `start` to `stop`."""
    zero, one = put(py.Constant(0), before).result, put(py.Constant(1), before).result
    (length := py_len.Len(reg)).insert_before(before)
    (head_slice := py_slice.Slice(zero, start, one)).insert_before(before)
    (head := py.indexing.GetItem(reg, head_slice.result)).insert_before(before)
    (tail_slice := py_slice.Slice(stop, length.result, one)).insert_before(before)
    (tail := py.indexing.GetItem(reg, tail_slice.result)).insert_before(before)
    (front := py.binop.Add(head.result, middle)).insert_before(before)
    (whole := py.binop.Add(front.result, tail.result)).insert_before(before)
    return whole.result


class ReferenceTypes(RewriteRule):
    """Retype explicit owned state after quantum operations become reference operations."""

    def rewrite_Block(self, node: ir.Block) -> RewriteResult:
        """Convert each region parameter to its corresponding reference type."""
        for value in node.args:
            value.type = squin_type(value.type)
        return RewriteResult()

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Convert each remaining result type before reference type inference."""
        for value in node.results:
            value.type = squin_type(value.type)
        return RewriteResult()


def bounded_list_lengths(kind: types.TypeAttribute) -> types.TypeAttribute:
    """Constrain unknown list lengths to integers without assuming a concrete size."""
    if isinstance(kind, types.Generic) and is_subtype(kind, ilist.IListType):
        element, length = kind.vars
        return ilist.IListType[
            bounded_list_lengths(element), types.Int if length == types.Any else length
        ]
    if (
        isinstance(kind, types.Generic)
        and is_subtype(kind, types.Tuple)
        and kind.vararg is None
    ):
        return types.Generic(
            tuple, *(bounded_list_lengths(member) for member in kind.vars)
        )
    return kind


class BoundListLengths(RewriteRule):
    """Give list lengths integer bounds before checking operation types."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Refine result types and the declared function signature."""
        changed = False
        for value in node.results:
            kind = bounded_list_lengths(value.type)
            changed |= value.type != kind
            value.type = kind
        if isinstance(node, func.Function):
            signature = node.signature
            inputs = tuple(bounded_list_lengths(kind) for kind in signature.inputs)
            output = bounded_list_lengths(signature.output)
            changed |= inputs != signature.inputs or output != signature.output
            node.signature = func.Signature(inputs=inputs, output=output)
            node.body.blocks[0].args[0].type = types.MethodType[list(inputs), output]
        return RewriteResult(has_done_something=changed)

    def rewrite_Block(self, node: ir.Block) -> RewriteResult:
        """Refine list lengths in block arguments."""
        changed = False
        for value in node.args:
            kind = bounded_list_lengths(value.type)
            changed |= value.type != kind
            value.type = kind
        return RewriteResult(has_done_something=changed)
