"""Check independent composition of wire state, gate and noise dialects."""

import pytest
from kirin import ir, types
from kirin.dialects import py, func
from kirin.interp.table import Signature

from bloqade.squin.wire import (
    WIRE_DIALECTS,
    GateKind,
    NoiseKind,
    gate,
    noise,
    state,
    stmts,
)
from bloqade.squin.wire.group import is_wire, reference_group, reference_kernel
from bloqade.squin.wire.types import register_type
from bloqade.squin.wire.typeinfer import InferWireTypes
from bloqade.squin.passes.wire_to_squin import WireToSquin
from bloqade.squin.analysis.validation.wire import WireValidation


@pytest.mark.parametrize(
    "selected, omitted, operation, excluded, kind, values",
    [
        (gate, noise, stmts.RegisterGate, stmts.RegisterNoise, GateKind.RX, (0.25,)),
        (
            noise,
            gate,
            stmts.RegisterNoise,
            stmts.RegisterGate,
            NoiseKind.DEPOLARIZE,
            (0.1,),
        ),
    ],
)
def test_a_group_can_select_gates_or_noise(
    selected, omitted, operation, excluded, kind, values
):
    group = reference_kernel.union([state.dialect, selected.dialect])
    assert omitted.dialect not in group.data
    registry = group.registry.interpreter(("typeinfer",))
    assert Signature(operation) in registry
    assert Signature(excluded) not in registry
    block = ir.Block(argtypes=(types.Any,))
    size = py.Constant(3)
    allocation = stmts.AllocRegister(size.result)
    params = [py.Constant(value) for value in values]
    applied = operation(
        kind, (allocation.result,), tuple(param.result for param in params)
    )
    block.stmts.extend(
        [
            size,
            allocation,
            *params,
            applied,
            stmts.FreeRegister(applied.results[0]),
            func.Return(size.result),
        ]
    )
    method = ir.Method(
        dialects=group,
        code=func.Function(
            sym_name="selected_dialects",
            body=ir.Region(block),
            signature=func.Signature(inputs=(), output=types.Int),
        ),
    )
    InferWireTypes(group)(method)
    assert applied.results[0].type == register_type(3)
    assert is_wire(method)
    WireValidation().check(method)
    restored = WireToSquin().emit(method)
    assert not is_wire(restored)
    assert not WIRE_DIALECTS & restored.dialects.data
    assert reference_group(group) == reference_kernel


def test_each_statement_belongs_to_one_wire_dialect():
    registrations = [stmt for dialect in WIRE_DIALECTS for stmt in dialect.stmts]
    assert len(registrations) == len(set(registrations)) == 23
    assert set(gate.dialect.stmts) == {stmts.Gate, stmts.RegisterGate}
    assert set(noise.dialect.stmts) == {stmts.Noise, stmts.RegisterNoise}
    assert all(
        stmt.dialect is dialect for dialect in WIRE_DIALECTS for stmt in dialect.stmts
    )
