"""Replace wire statements with Jeff quantum statements.

A Jeff register value carries its static length in its type, such as `qureg(3)`,
whenever the rewrite knows that length. An operation that continues a register
keeps the type of its input.
"""

from kirin import ir, types
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.qubit import stmts as qubit_stmts
from bloqade.types import item_type
from bloqade.constants import constant_int
from bloqade.jeff.forms import GATES
from bloqade.jeff.types import IntArrayType, qureg, is_subtype, qureg_length
from bloqade.squin.wire import stmts as wire
from bloqade.jeff.dialects import stmts

from .kinds import put, radians, replace, bitwidth

DIRECT: dict[type[ir.Statement], type[ir.Statement]] = {
    wire.Alloc: stmts.Alloc,
    wire.Free: stmts.Free,
    wire.FreeRegister: stmts.RegFree,
    wire.Borrow: stmts.Extract,
    wire.Release: stmts.Insert,
    wire.Length: stmts.RegLength,
    wire.Take: stmts.Extract,
    wire.Put: stmts.Insert,
    wire.TakeSlice: stmts.ExtractSlice,
    wire.PutSlice: stmts.InsertSlice,
    wire.SplitRegister: stmts.RegSplit,
    wire.JoinRegister: stmts.RegJoin,
    wire.DiscardRegister: stmts.RegFree,
}
"""Map each wire statement to the Jeff statement with the same operands and results."""

CONTINUES = (
    wire.Borrow,
    wire.Release,
    wire.Length,
    wire.Take,
    wire.Put,
    wire.TakeSlice,
    wire.PutSlice,
)
"""The wire statements whose first result continues their register operand."""


class Quantum(RewriteRule):
    """Replace each wire statement and measurement predicate with Jeff."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Rewrite `node` if it has a Jeff form, and leave any other statement."""
        if type(node) in DIRECT:
            made = put(DIRECT[type(node)](*node.args), node)
            if isinstance(node, CONTINUES):
                made.results[0].type = node.args[0].type
            if isinstance(node, wire.TakeSlice):
                made.results[1].type = qureg(constant_int(node.length))
            replace(node, *made.results)
        elif isinstance(node, wire.AllocRegister):
            made = put(stmts.RegAlloc(node.size), node)
            made.result.type = qureg(constant_int(node.size))
            replace(node, made.result)
        elif isinstance(node, wire.PackRegister):
            replace(node, put(stmts.RegCreate(node.wires), node).result)
        elif isinstance(node, wire.RegisterOperation):
            replace(node, *broadcast(node))
        elif isinstance(node, wire.Operation):
            if not supported(node):
                return RewriteResult()
            replace(node, *scalar(node))
        elif isinstance(node, qubit_stmts.IsOne):
            # A measurement bit is its own test for one.
            replace(node, node.measurements)
        elif isinstance(node, qubit_stmts.IsZero):
            replace(node, negated(node))
        else:
            return RewriteResult()
        return RewriteResult(has_done_something=True)


def supported(node: wire.Operation) -> bool:
    """Check whether the wire operation `node` has a Jeff form."""
    if isinstance(node, (wire.Gate, wire.RegisterGate)):
        return node.kind in GATES
    return isinstance(
        node, (wire.Measure, wire.Reset, wire.RegisterMeasure, wire.RegisterReset)
    )


def scalar(node: wire.Operation) -> tuple[ir.SSAValue, ...]:
    """Insert the Jeff form of the scalar operation `node` and return its results.

    Gate angles change from turns to radians. A Jeff gate acts on one group of
    wires, so a gate on several groups becomes one Jeff gate per group. Jeff puts
    targets before controls, so the results go back to the wire order.
    """
    if isinstance(node, wire.Measure):
        measured = put(stmts.MeasureNd(node.wire), node)
        return measured.result_wire, measured.bit
    if isinstance(node, wire.Reset):
        return (put(stmts.Reset(node.wire), node).result,)
    assert isinstance(node, wire.Gate)
    form = GATES[node.kind]
    angles = tuple(radians(angle, node) for angle in node.params)
    results: list[ir.SSAValue] = []
    for group in node.groups:
        controls, targets = group[: form.controls], group[form.controls :]
        gate = stmts.Gate(
            targets, controls, angles, gate_name=form.name, adjoint=node.adjoint
        )
        made = put(gate, node)
        count = len(targets)
        results.extend((*made.results[count:], *made.results[:count]))
    return tuple(results)


def negated(node: qubit_stmts.IsZero) -> ir.SSAValue:
    """Insert the negation of each measurement bit that `node` tests.

    A bit list is a Jeff array whose length comes from the statement that builds it.
    """
    bits = node.measurements
    if not is_subtype(bits.type, IntArrayType):
        return put(stmts.IntNot(bits), node).result
    match bits.owner:
        case stmts.IntArrayCreate(values=values):
            size = len(values)
        case stmts.IntArrayConst(values=values):
            size = len(values)
        case _:
            raise ir.ValidationError(node, f"{bits} is a bit array of unknown length")
    items: list[ir.SSAValue] = []
    for position in range(size):
        at = put(stmts.ConstInt(value=position), node).result
        bit = put(stmts.IntArrayGet(bits, at, bitwidth=1), node).result
        items.append(put(stmts.IntNot(bit), node).result)
    return put(stmts.IntArrayCreate(tuple(items), bitwidth=1), node).result


def applied(
    node: wire.RegisterOperation,
    qubits: list[ir.SSAValue],
    before: ir.Statement,
) -> tuple[ir.SSAValue, ...]:
    """Insert the scalar form of the register operation `node` and return its results.

    `qubits` holds one Jeff wire per register of `node`.
    """
    made = node.scalar(tuple(qubits))
    made.insert_before(before)
    results = scalar(made)
    made.delete()
    return results


def broadcast(node: wire.RegisterOperation) -> tuple[ir.SSAValue, ...]:
    """Insert the Jeff form of the register operation `node` and return its results.

    Jeff gates act on single qubits. If the registers have a static length, the
    rewrite emits the scalar operation once per position. Otherwise it emits a Jeff
    loop that fills arrays of runtime length.
    """
    if not supported(node):
        raise ir.ValidationError(node, f"Jeff has no form for '{node.label}'.")
    registers = list(node.linear)
    lengths = [qureg_length(register.type) for register in registers]
    if node.truncates:
        size = None if None in lengths else min(n for n in lengths if n is not None)
    else:
        size = next((n for n in lengths if n is not None), None)
    widths = [bitwidth(item_type(result.type)) for result in node.classical]
    if size is None:
        return looped(node, registers, widths)
    return unrolled(node, registers, widths, size)


def unrolled(
    node: wire.RegisterOperation,
    registers: list[ir.SSAValue],
    widths: list[int],
    size: int,
) -> tuple[ir.SSAValue, ...]:
    """Emit the scalar operation at each of the `size` positions of the registers."""
    collected: list[list[ir.SSAValue]] = [[] for _ in widths]
    for position in range(size):
        at = put(stmts.ConstInt(value=position), node).result
        qubits: list[ir.SSAValue] = []
        for k, register in enumerate(registers):
            made = put(stmts.Extract(register, at), node)
            made.result_reg.type = register.type
            registers[k] = made.result_reg
            qubits.append(made.wire)
        outputs = applied(node, qubits, node)
        for k, register in enumerate(registers):
            inserted = put(stmts.Insert(register, at, outputs[k]), node)
            inserted.result.type = register.type
            registers[k] = inserted.result
        for k, items in enumerate(collected):
            items.append(outputs[len(registers) + k])
    arrays = [
        put(stmts.IntArrayCreate(tuple(items), bitwidth=width), node).result
        for items, width in zip(collected, widths, strict=True)
    ]
    return (*registers, *arrays)


def looped(
    node: wire.RegisterOperation,
    registers: list[ir.SSAValue],
    widths: list[int],
) -> tuple[ir.SSAValue, ...]:
    """Emit a Jeff loop that applies the scalar operation at each register position.

    Each classical result goes into an array of runtime length. The loop body reads
    the classical operands of `node` from the enclosing block. The pass
    `IsolateRegions` in `isolate.py` then adds each such operand to the loop state,
    because a Jeff region takes every outside value as an input.
    """
    # Without truncation, every register has the length of the first one.
    sizes: list[ir.SSAValue] = []
    for k in range(len(registers) if node.truncates else 1):
        made = put(stmts.RegLength(registers[k]), node)
        made.result_reg.type = registers[k].type
        registers[k] = made.result_reg
        sizes.append(made.length)
    size = sizes[0]
    for other in sizes[1:]:
        size = put(stmts.IntMinS(size, other), node).result
    arrays = [
        put(stmts.IntArrayZero(size, bitwidth=width), node).result for width in widths
    ]
    body = ir.Block()
    index = body.args.append_from(types.Int, "index")
    carried: list[ir.SSAValue] = [
        body.args.append_from(register.type) for register in registers
    ]
    bits: list[ir.SSAValue] = [body.args.append_from(IntArrayType) for _ in arrays]
    end = stmts.Yield()
    body.stmts.append(end)
    qubits: list[ir.SSAValue] = []
    for k, register in enumerate(carried):
        made = put(stmts.Extract(register, index), end)
        made.result_reg.type = register.type
        carried[k] = made.result_reg
        qubits.append(made.wire)
    outputs = applied(node, qubits, end)
    for k, register in enumerate(carried):
        inserted = put(stmts.Insert(register, index, outputs[k]), end)
        inserted.result.type = register.type
        carried[k] = inserted.result
    for k, array in enumerate(bits):
        set_item = stmts.IntArraySet(array, index, outputs[len(carried) + k])
        bits[k] = put(set_item, end).result
    end.replace_by(stmts.Yield(*carried, *bits))
    start = put(stmts.ConstInt(value=0), node).result
    step = put(stmts.ConstInt(value=1), node).result
    region = ir.Region(body)
    loop = put(stmts.For(start, size, step, (*registers, *arrays), region), node)
    return tuple(loop.results)
