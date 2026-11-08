"""Pack quantum containers for helper calls and restore their original locations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kirin import ir, lowering
from kirin.dialects import py, func

from bloqade.squin.wire import stmts
from bloqade.analysis.indices import IndexExpr
from bloqade.squin.emit.wire.base import WireFrame
from bloqade.squin.emit.wire.values import (
    Qubit,
    Value,
    Single,
    Element,
    Register,
    known_items,
)
from bloqade.squin.emit.wire.functions import call_converted
from bloqade.squin.rewrite.wire.signature import quantum_type

if TYPE_CHECKING:
    from .core import Python


def flatten(
    value: Value, at: ir.Statement
) -> tuple[tuple[Single, ...], tuple[int, ...]]:
    """Flatten a rectangular quantum container and retain its dimensions."""
    if isinstance(value, (Qubit, Element)):
        return (value,), ()
    items = known_items(value, at)
    if items is None:
        raise lowering.BuildError(
            "A helper argument requires a whole register or a quantum container of known shape."
        )
    children = tuple(flatten(item, at) for item in items)
    shapes = {shape for _, shape in children}
    if len(shapes) > 1:
        raise lowering.BuildError(
            "A quantum container argument must have a rectangular shape."
        )
    shape = (len(items), *next(iter(shapes), ()))
    return tuple(wire for wires, _ in children for wire in wires), shape


def invoke(frontend: Python, frame: WireFrame, stmt: func.Invoke) -> Value:
    """Call the wire helper and restore each temporary register to its source locations."""
    source, wired, layout = frontend.compiler.callee(stmt.callee)
    frontend.emitter.converted = {source: wired}
    parameters = source.callable_region.blocks[0].args[1:]
    inputs = list(stmt.inputs)
    packed: list[tuple[Register, tuple[Single, ...]]] = []
    for position, (argument, parameter) in enumerate(
        zip(inputs, parameters, strict=True)
    ):
        value = frame.get(argument)
        if quantum_type(parameter.type) is None or not isinstance(value, tuple):
            continue
        locations, shape = flatten(value, stmt)
        wires = tuple(
            frontend.emitter.acquire(frame, location) for location in locations
        )
        node = frame.push(stmts.PackRegister(wires))
        register = Register(node.result, IndexExpr(shape[0]), shape[1:])
        frame.own(register, local=False)
        packed.append((register, locations))
        inputs[position] = frontend.value(register)
        frame.entries[inputs[position]] = register
    call = func.Invoke(tuple(inputs), callee=source)
    call.source = stmt.source
    try:
        result = call_converted(frontend.emitter, frame, call, layout)
    finally:
        call.drop_all_references()
    for register, locations in packed:
        current = frame.latest.pop(register.root)
        for position, location in enumerate(locations):
            index = frame.push(py.Constant(position)).result
            taken = frame.push(stmts.Take(current, index))
            current = taken.register_out
            frontend.emitter.restore(frame, location, taken.wire)
        frame.push(stmts.DiscardRegister(current))
    return result
