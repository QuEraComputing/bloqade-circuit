"""Turn wire squin back into reference squin with the kirin rewrite rules of `FromWire`.

Every wire statement hands each wire on to a result. So a qubit keeps one
reference squin value along its whole chain of wires. The rule for each statement
inserts its reference statements and returns one value for each result, and
`FromWireStatements` replaces the results with these values. A result that
continues a wire reads as the qubit of that wire. Once the rule for `Alloc`
replaces the first wire of a chain with a `qubit.new` result, every later
statement on the chain reads that qubit. The order of the rewrites makes no
difference, except for the `PutSlice` shortcut that `restores` describes.

The rules for loops and branches run after the other rules. They remove the
carried wires from the initializers, the block arguments and the yields.

An in-out call returns the wires of its qubit arguments after its ordinary
outputs. The call rule reads each returned wire as the argument that went in. The
signature rule turns each wire parameter back into a qubit parameter and drops the
returned wires from the return statement.
"""

from dataclasses import dataclass
from collections.abc import Mapping

from kirin import ir, types
from kirin.rewrite import Walk, Chain, DeadCodeElimination
from kirin.dialects import py, scf, func, ilist
from kirin.dialects.py import len as py_len, slice as py_slice
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.qubit import stmts as qubit_stmts, qalloc
from bloqade.types import QubitType, is_subtype, output_types
from bloqade.constants import constant_int
from bloqade.squin.wire import stmts
from bloqade.squin.wire.group import is_wire, reference_group
from bloqade.squin.wire.types import RegisterType, is_linear
from bloqade.squin.wire.traits import Threads, ReferenceForm
from bloqade.squin.wire.returns import (
    KEY as RETURN_POLICY,
    ReturnPolicy,
    return_policy,
    quantum_parameter_count,
)
from bloqade.squin.rewrite.wire.tools import (
    Retype,
    CheckedFixpoint,
    put,
    pack,
    replace,
    reachable,
    set_signature,
)
from bloqade.squin.rewrite.wire.sources import entry_of
from bloqade.squin.rewrite.wire.signature import packed_type


def squin_type(typ: types.TypeAttribute) -> types.TypeAttribute:
    """Return the reference squin type of the wire squin type `typ`."""
    if is_subtype(typ, RegisterType):
        return ilist.IListType[QubitType, types.Any]
    if is_linear(typ):
        return QubitType
    if isinstance(typ, types.Generic) and is_subtype(typ, types.Tuple):
        return types.Generic(tuple, *(squin_type(member) for member in typ.vars))
    return typ


def kept_outputs(
    signature: func.Signature, policy: ReturnPolicy
) -> tuple[types.TypeAttribute, ...]:
    """Return the ordinary output types of a wire function with `signature`.

    `PreserveArguments` places the updated quantum arguments after the classical results.
    If the function has no quantum arguments, conversion keeps its entire result.
    This preserves the shape of a tuple that holds one item.
    """
    borrowed = (
        quantum_parameter_count(signature)
        if policy is ReturnPolicy.PreserveArguments
        else 0
    )
    if not borrowed:
        none = is_subtype(signature.output, types.NoneType)
        return () if none else (squin_type(signature.output),)
    outputs = output_types(signature.output)
    return tuple(squin_type(typ) for typ in outputs[: len(outputs) - borrowed])


@dataclass
class FromWireStatements(RewriteRule):
    """Replace each wire statement outside a loop or branch with reference squin."""

    wire_dialects: tuple[ir.Dialect, ...] = ()
    """Hold the dialects of the wire statements that other dialects add."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Rewrite `node` if it belongs to the wire dialect or a wire extension."""
        if node.dialect in self.wire_dialects and not node.has_trait(ReferenceForm):
            raise ir.ValidationError(
                node,
                f"The wire statement '{node.name}' has no ReferenceForm trait, so"
                " WireToSquin cannot rebuild it.",
            )
        if isinstance(node, stmts.Operation):
            values = self.operation(node)
        elif (form := node.get_trait(ReferenceForm)) is not None:
            values = self.extension(node, form)
        else:
            values = state_values(node)
            if values is None:
                return RewriteResult()
        replace(node, *values)
        return RewriteResult(has_done_something=True)

    def extension(
        self, node: ir.Statement, form: ReferenceForm
    ) -> tuple[ir.SSAValue, ...]:
        """Return the reference value of each result of a statement of another dialect.

        `form` returns one value for each result that no `Threads` pair continues.
        Each continuing result reads as its operand.
        """
        threads = node.get_trait(Threads)
        continued = dict(
            (result, operand)
            for operand, result in ([] if threads is None else threads.threads(node))
        )
        fresh = form.rebuild(node)
        count = len(node.results) - len(continued)
        if len(fresh) != count:
            raise ir.ValidationError(
                node,
                f"The ReferenceForm of '{node.name}' returned {len(fresh)} values"
                f" for {count} results that no Threads pair continues.",
            )
        rebuilt = iter(fresh)
        return tuple(
            continued[result] if result in continued else next(rebuilt)
            for result in node.results
        )

    def operation(self, node: stmts.Operation) -> tuple[ir.SSAValue, ...]:
        """Insert the squin statement of the wire operation `node` before it.

        On a scalar operation, qubit field `j` of the squin statement gets the list
        of wire `j` of every group. So `Gate(kind=cx, wires=(c0, t0, c1, t1))`
        becomes `cx([c0, c1], [t0, t1])`. A scalar result, such as a measurement
        result, becomes item 0 of the list result of the squin statement. On a
        register operation, each register becomes the list of qubits that it holds,
        and each list result stays a list.
        """
        entry = entry_of(node)
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
        classical: list[ir.SSAValue] = []
        for result, value in zip(
            node.classical, entry.result_values(made), strict=True
        ):
            if scalar:
                zero = put(py.Constant(0), node)
                item = put(py.GetItem(value, zero.result), node)
                item.result.type = result.type
                value = item.result
            classical.append(value)
        replacements = dict(zip(node.outputs, node.linear, strict=True))
        replacements.update(zip(node.classical, classical, strict=True))
        return tuple(replacements[result] for result in node.results)


def from_alloc(node: stmts.Alloc) -> tuple[ir.SSAValue, ...]:
    """Read the wire of an allocation as a new qubit."""
    return (put(qubit_stmts.New(), node).result,)


def from_alloc_register(node: stmts.AllocRegister) -> tuple[ir.SSAValue, ...]:
    """Read the register of an allocation as a call of `qalloc`."""
    call = put(func.Invoke((node.size,), callee=qalloc), node)
    call.result.type = qalloc.return_type
    return (call.result,)


def from_borrow(node: stmts.Borrow | stmts.Take) -> tuple[ir.SSAValue, ...]:
    """Read the borrowed wire as the qubit at its index."""
    item = put(py.GetItem(node.register, node.index), node)
    item.result.type = QubitType
    return node.register, item.result


def from_put(node: stmts.Put) -> tuple[ir.SSAValue, ...]:
    """Read the filled register as the list with the qubit at its index."""
    start = normalized_index(node.register, node.index, node)
    one = put(py.Constant(1), node).result
    stop = put(py.Add(start, one), node).result
    middle = put(ilist.New((node.wire,), elem_type=QubitType), node).result
    return (splice(node.register, start, stop, middle, node),)


def normalized_index(
    register: ir.SSAValue, index: ir.SSAValue, node: ir.Statement
) -> ir.SSAValue:
    """Convert a negative index to its position from the start of the register."""
    constant = constant_int(index)
    if constant is not None and constant >= 0:
        return index
    length = put(py_len.Len(register), node).result
    if constant is not None:
        return put(py.Add(length, index), node).result
    zero = put(py.Constant(0), node).result
    negative = put(py.cmp.Lt(index, zero), node).result
    adjusted = py.Add(length, index)
    then = ir.Block([adjusted, scf.Yield(adjusted.result)], argtypes=(types.Bool,))
    otherwise = ir.Block([scf.Yield(index)], argtypes=(types.Bool,))
    return put(
        scf.IfElse(negative, ir.Region(then), ir.Region(otherwise)), node
    ).results[0]


def from_pack(node: stmts.PackRegister) -> tuple[ir.SSAValue, ...]:
    """Read the packed register as the list of its qubits."""
    return (put(ilist.New(node.wires, elem_type=QubitType), node).result,)


def from_join(node: stmts.JoinRegister) -> tuple[ir.SSAValue, ...]:
    """Read the joined register as the concatenation of both lists."""
    return (put(py.Add(node.first, node.second), node).result,)


def from_split(node: stmts.SplitRegister) -> tuple[ir.SSAValue, ...]:
    """Read both parts of the split register as slices of its list."""
    zero = put(py.Constant(0), node).result
    one = put(py.Constant(1), node).result
    length = put(py_len.Len(node.register), node).result
    head = put(py_slice.Slice(zero, node.index, one), node).result
    tail = put(py_slice.Slice(node.index, length, one), node).result
    return (
        put(py.GetItem(node.register, head), node).result,
        put(py.GetItem(node.register, tail), node).result,
    )


def from_take_slice(node: stmts.TakeSlice) -> tuple[ir.SSAValue, ...]:
    """Read the moved range as a slice of the register list."""
    start = normalized_index(node.register, node.start, node)
    stop = put(py.Add(start, node.length), node).result
    one = put(py.Constant(1), node).result
    part = put(py_slice.Slice(start, stop, one), node).result
    return node.register, put(py.GetItem(node.register, part), node).result


def from_put_slice(node: stmts.PutSlice) -> tuple[ir.SSAValue, ...]:
    """Read the filled register as the list with the slice in its range.

    If the slice returns to the range that it left, the register list holds the
    same qubit references as before.
    """
    if restores(node):
        return (node.register,)
    start = normalized_index(node.register, node.start, node)
    length = put(py_len.Len(node.slice_register), node).result
    stop = put(py.Add(start, length), node).result
    return (splice(node.register, start, stop, node.slice_register, node),)


def from_release(node: stmts.Release) -> tuple[ir.SSAValue, ...]:
    """Read the register after a release as the register before it."""
    return (node.register,)


def from_length(node: stmts.Length) -> tuple[ir.SSAValue, ...]:
    """Read the length of a register as the length of its list."""
    return node.register, put(py_len.Len(node.register), node).result


def from_free(
    node: stmts.Free | stmts.FreeRegister | stmts.DiscardRegister,
) -> tuple[ir.SSAValue, ...]:
    """Drop a free, which has no reference squin form."""
    return ()


def state_values(node: ir.Statement) -> tuple[ir.SSAValue, ...] | None:
    """Insert the reference form of a state operation and return its replacement values."""
    match node:
        case stmts.Alloc():
            return from_alloc(node)
        case stmts.AllocRegister():
            return from_alloc_register(node)
        case stmts.Borrow() | stmts.Take():
            return from_borrow(node)
        case stmts.Put():
            return from_put(node)
        case stmts.PackRegister():
            return from_pack(node)
        case stmts.JoinRegister():
            return from_join(node)
        case stmts.SplitRegister():
            return from_split(node)
        case stmts.TakeSlice():
            return from_take_slice(node)
        case stmts.PutSlice():
            return from_put_slice(node)
        case stmts.Release():
            return from_release(node)
        case stmts.Length():
            return from_length(node)
        case stmts.Free() | stmts.FreeRegister() | stmts.DiscardRegister():
            return from_free(node)
    return None


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
        else_yield = node.else_body.blocks[0].last_stmt
        assert isinstance(else_yield, scf.Yield)
        for k in dropped:
            value = then_yield.values[k]
            if value is not else_yield.values[k] or node.is_ancestor(value.owner):
                raise ir.ValidationError(
                    node,
                    "Both branches must yield the same qubit, and the qubit must"
                    " exist before the branch.",
                )
            node.results[k].replace_by(value)
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

    `kernels` maps each wire method to its squin kernel. A returned wire of an
    in-out argument becomes the argument itself.
    """

    kernels: Mapping[ir.Method, ir.Method]

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Rewrite `node` if it calls a wire squin method."""
        if not isinstance(node, func.Invoke) or not is_wire(node.callee):
            return RewriteResult()
        callee = node.callee.code
        assert isinstance(callee, func.Function)
        policy = return_policy(callee)
        call = put(func.Invoke(node.inputs, callee=self.kernels[node.callee]), node)
        kept = kept_outputs(callee.signature, policy)
        call.result.type = packed_type(kept)
        borrowed = (
            [a for a, k in zip(node.inputs, callee.signature.inputs) if is_linear(k)]
            if policy is ReturnPolicy.PreserveArguments
            else []
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
                replace(item, output(index.value.unwrap(), item))
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
        policy = return_policy(node)
        kept = kept_outputs(signature, policy)
        block = node.body.blocks[0]
        returned = block.last_stmt
        assert isinstance(returned, func.Return)
        # Without in-out wires, the function returns its source result whole.
        if policy is ReturnPolicy.PreserveArguments and quantum_parameter_count(
            signature
        ):
            if len(outputs) == 1:
                values = [returned.value]
            elif isinstance(made := returned.value.owner, py.tuple.New):
                values = list(made.args)
            else:
                raise ir.ValidationError(
                    returned, "An in-out function must build its results with a tuple."
                )
            put(func.Return(pack(values[: len(kept)], returned)), returned)
            returned.delete()
        for arg in block.args[1:]:
            arg.type = squin_type(arg.type)
        inputs = tuple(squin_type(k) for k in signature.inputs)
        set_signature(node, inputs, packed_type(kept))
        return RewriteResult(has_done_something=True)


@dataclass
class FromWire:
    """Convert wire squin methods into squin kernels, one copy per method."""

    wire_dialects: tuple[ir.Dialect, ...] = ()
    """Hold the dialects of the wire statements that other dialects add.

    The squin kernels leave these dialects out of their dialect groups.
    """

    def convert(self, method: ir.Method) -> dict[ir.Method, ir.Method]:
        """Return the squin kernel of `method` and of each wire method that it calls.

        The result maps each wire method to its kernel, callees first.
        """
        kernels = {
            wired: wired.similar(reference_group(wired.dialects, self.wire_dialects))
            for wired in reachable(method)
        }
        for kernel in kernels.values():
            self.rewrite(kernel, kernels)
        return kernels

    def rewrite(
        self, method: ir.Method, kernels: Mapping[ir.Method, ir.Method]
    ) -> RewriteResult:
        """Run the statement rules, then apply the function return policy.

        `PreserveArguments` removes the carried wires from loops, branches and
        returns. Dead-code elimination then removes unused wire values.
        `ExplicitReturns` keeps quantum results and converts their types to Squin
        reference types.
        """
        statements = Walk(
            Chain(FromWireStatements(self.wire_dialects), FromWireCalls(kernels))
        )
        result = CheckedFixpoint(statements).rewrite(method.code)
        assert isinstance(method.code, func.Function)
        match return_policy(method.code):
            case ReturnPolicy.ExplicitReturns:
                result = Walk(Retype(squin_type)).rewrite(method.code).join(result)
            case ReturnPolicy.PreserveArguments:
                regions = Walk(Chain(FromWireRegions(), FromWireSignature()))
                result = CheckedFixpoint(regions).rewrite(method.code).join(result)
                cleanup = CheckedFixpoint(Walk(DeadCodeElimination()))
                result = cleanup.rewrite(method.code).join(result)
        method.code.attributes.pop(RETURN_POLICY, None)
        return result


def restores(node: stmts.PutSlice) -> bool:
    """Check whether `node` puts a slice back into the range that it came from.

    The check reads the reference form of the slice, `register[start:stop]`, so it
    holds only after the `TakeSlice` rule ran on the slice. Kirin's `Walk` visits
    the `TakeSlice` first, because it defines the slice. If the check fails, the
    `PutSlice` rule splices the slice back in, which gives the same qubits.
    """
    part = node.slice_register.owner
    if not isinstance(part, py.GetItem) or part.obj is not node.register:
        return False
    bounds = part.index.owner
    return isinstance(bounds, py_slice.Slice) and same(bounds.start, node.start)


def same(left: ir.SSAValue, right: ir.SSAValue) -> bool:
    """Check whether 2 integer values come from equal constants and arithmetic."""
    if left is right:
        return True
    a, b = left.owner, right.owner
    if isinstance(a, py.Constant) and isinstance(b, py.Constant):
        return a.value == b.value
    return (
        type(a) is type(b)
        and isinstance(a, (py.Add, py.Sub, py.Mult))
        and all(same(x, y) for x, y in zip(a.args, b.args, strict=True))
    )


def splice(
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
