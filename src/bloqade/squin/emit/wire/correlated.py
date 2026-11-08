"""Emit correlated loss on whole groups while preserving their shared event."""

from kirin import ir, types
from kirin.dialects import py, scf

from bloqade.squin.wire import stmts
from bloqade.analysis.indices import Slice, IndexExpr
from bloqade.squin.noise.stmts import CorrelatedQubitLoss
from bloqade.squin.wire.errors import WireConversionError

from .base import EmitWire, WireFrame
from .values import View, Value, Register, singles, known_items


def group_loss(
    emit: EmitWire, frame: WireFrame, group: Value, probability: ir.SSAValue
) -> None:
    """Apply one loss event to a contiguous group or a list of known qubits."""
    if (
        isinstance(group, (Register, View))
        and not group.row_shape
        and (isinstance(group, Register) or group.span.step == 1)
    ):
        emit.operate(
            frame, (group,), lambda inputs: stmts.CorrelatedLoss(inputs[0], probability)
        )
        return
    items = known_items(group, frame.statement)
    if items is None:
        raise WireConversionError(
            "A correlated loss group requires resolved qubit locations.",
            frame.statement,
        )
    locations = singles(items, frame.statement)
    inputs = tuple(emit.acquire(frame, location) for location in locations)
    packed = frame.push(stmts.PackRegister(inputs)).result
    register = frame.push(stmts.CorrelatedLoss(packed, probability)).register_out
    outputs: list[ir.SSAValue] = []
    for position in range(len(inputs)):
        index = frame.push(py.Constant(position)).result
        taken = frame.push(stmts.Take(register, index))
        register = taken.register_out
        outputs.append(taken.wire)
    frame.push(stmts.DiscardRegister(register))
    for location, value in zip(locations, outputs, strict=True):
        emit.restore(frame, location, value)


def emit_correlated(
    emit: EmitWire, frame: WireFrame, stmt: CorrelatedQubitLoss
) -> tuple[()]:
    """Lower known groups directly or iterate over rows of a runtime register."""
    groups = frame.get(stmt.qubits)
    probability = emit.classical_value(frame, frame.get(stmt.p))
    items = known_items(groups, stmt)
    if items is not None:
        for group in items:
            group_loss(emit, frame, group, probability)
        return ()
    if (
        not isinstance(groups, Register)
        or len(groups.row_shape) != 1
        or groups.row_shape[0] is None
    ):
        raise WireConversionError(
            "Correlated loss requires a known number of qubits in each group.", stmt
        )
    count = emit.length_value(frame, groups)
    zero = frame.push(py.Constant(0)).result
    one = frame.push(py.Constant(1)).result
    from kirin.dialects.ilist.stmts import Range

    iterable = frame.push(Range(zero, count, one)).result
    body = WireFrame(stmt)
    body.current_stmt = stmt
    index = body.output.args.append_from(types.Int)
    current = frame.latest[groups.root]
    body.latest[groups.root] = body.output.args.append_from(current.type)
    body.entries[index] = index
    span = Slice(
        IndexExpr.of(index).scale(groups.row_shape[0]),
        1,
        IndexExpr(groups.row_shape[0]),
    )
    group_loss(emit, body, View(groups.root, span), probability)
    body.push(scf.Yield(body.latest[groups.root]))
    loop = frame.push(scf.For(iterable, ir.Region(body.output), current))
    frame.latest[groups.root] = loop.results[0]
    return ()
