"""Check parameter types for scalar and register operations."""

import pytest
from kirin import ir, types
from kirin.dialects import py, func, ilist
from kirin.ir.exception import ValidationErrorGroup

from bloqade.squin.wire import GateKind, NoiseKind, stmts, kernel
from bloqade.squin.wire.typeinfer import InferWireTypes
from bloqade.squin.analysis.validation.wire import WireValidation


def program(kind, values, register):
    """Build a complete wire program that applies the operation with these parameters."""
    block = ir.Block(argtypes=(types.Any,))
    size = py.Constant(2)
    block.stmts.append(size)
    allocations = [
        stmts.AllocRegister(size.result) if register else stmts.Alloc()
        for _ in range(kind.qubit_count)
    ]
    parameters = [py.Constant(value) for value in values]
    block.stmts.extend([*allocations, *parameters])
    if isinstance(kind, GateKind):
        operation = stmts.RegisterGate if register else stmts.Gate
    else:
        operation = stmts.RegisterNoise if register else stmts.Noise
    applied = operation(
        kind,
        tuple(allocation.result for allocation in allocations),
        tuple(parameter.result for parameter in parameters),
    )
    free = stmts.FreeRegister if register else stmts.Free
    end = py.Constant(0)
    block.stmts.extend(
        [
            applied,
            *(free(value) for value in applied.results),
            end,
            func.Return(end.result),
        ]
    )
    method = ir.Method(
        dialects=kernel,
        code=func.Function(
            sym_name="parameters",
            body=ir.Region(block),
            signature=func.Signature(inputs=(), output=types.Int),
        ),
    )
    InferWireTypes(kernel)(method)
    return method


@pytest.mark.parametrize("kind", [*GateKind, *NoiseKind])
@pytest.mark.parametrize("register", [False, True])
@pytest.mark.parametrize("value", [0, 0.125])
def test_numeric_parameters_pass_for_every_kind(kind, register, value):
    values = (value,) * kind.param_count
    if kind is NoiseKind.TWO_QUBIT_PAULI_CHANNEL:
        values = (ilist.IList([value] * 15, elem=types.PyClass(type(value))),)
    WireValidation().check(program(kind, values, register))


@pytest.mark.parametrize(
    "kind", [kind for kind in (*GateKind, *NoiseKind) if kind.param_count]
)
@pytest.mark.parametrize("register", [False, True])
@pytest.mark.parametrize("invalid", ["invalid", None, 1j])
def test_invalid_parameters_fail_for_every_parameter_position(kind, register, invalid):
    for index in range(kind.param_count):
        values = [0.125] * kind.param_count
        values[index] = invalid
        with pytest.raises(ValidationErrorGroup, match=f"Parameter {index}"):
            WireValidation().check(program(kind, values, register))


@pytest.mark.parametrize("register", [False, True])
@pytest.mark.parametrize(
    "invalid",
    [
        0.1,
        ilist.IList([0.1] * 14, elem=types.Float),
        ilist.IList([0.1] * 16, elem=types.Float),
        ilist.IList(["invalid"] * 15, elem=types.String),
    ],
)
def test_two_qubit_pauli_requires_fifteen_numeric_probabilities(register, invalid):
    with pytest.raises(ValidationErrorGroup, match="Parameter 0"):
        WireValidation().check(
            program(NoiseKind.TWO_QUBIT_PAULI_CHANNEL, (invalid,), register)
        )


@pytest.mark.parametrize("kind", [GateKind.RX, NoiseKind.DEPOLARIZE])
@pytest.mark.parametrize("register", [False, True])
def test_scalar_parameters_reject_probability_vectors(kind, register):
    with pytest.raises(ValidationErrorGroup, match="Parameter 0"):
        WireValidation().check(
            program(kind, (ilist.IList([0.1] * 15, elem=types.Float),), register)
        )
