"""Check that full conversion rejects every surviving reference operation."""

import pytest
from kirin import ir, types
from kirin.dialects import py, func, ilist
from test_roundtrip import ladder

from bloqade import squin
from bloqade.types import QubitType
from bloqade.squin.wire import Gate, GateKind, Operation, WireConversionError
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.analysis.validation.wire import StructureValidation
from bloqade.squin.analysis.validation.wire.target import ConversionTarget


@squin.kernel
def correlated():
    qs = [squin.qubit.new(), squin.qubit.new()]
    squin.broadcast.x(qs)
    squin.broadcast.correlated_qubit_loss(0.0, [qs])
    return squin.broadcast.measure(qs)


@squin.kernel
def calls_correlated():
    return correlated()


@squin.kernel
def conditional_correlated(flag: bool):
    if flag:
        correlated()


@pytest.mark.parametrize(
    "kernel", [correlated, calls_correlated, conditional_correlated]
)
def test_full_conversion_rejects_an_operation_without_a_lowering(kernel):
    before = kernel.code.print_str()
    with pytest.raises(WireConversionError, match="correlated_qubit_loss"):
        SquinToWire().emit(kernel)
    assert kernel.code.print_str() == before


def test_conversion_checks_wire_operand_types():
    wired = SquinToWire().emit(ladder)
    assert any(isinstance(node, Operation) for node in wired.callable_region.walk())
    assert StructureValidation().run(wired)[1] == []
    block = wired.callable_region.blocks[0]
    head = block.first_stmt
    number = py.Constant(1)
    number.insert_before(head)
    Gate(GateKind.H, (number.result,)).insert_before(head)
    assert StructureValidation().run(wired)[1]


@squin.kernel
def unsupported_only():
    qs = [squin.qubit.new(), squin.qubit.new()]
    squin.broadcast.correlated_qubit_loss(0.0, [qs])


def test_an_unsupported_operation_requires_no_bridge_to_fail_conversion():
    with pytest.raises(WireConversionError, match="correlated_qubit_loss"):
        SquinToWire().emit(unsupported_only)


@pytest.mark.parametrize(
    "kind",
    [
        QubitType,
        ilist.IListType[QubitType, types.Any],
        types.Generic(tuple, types.Int, QubitType),
        types.Generic(tuple, types.Vararg(QubitType)),
        types.Union(QubitType, types.NoneType),
        types.TypeVar("Q", bound=types.Union(QubitType, types.NoneType)),
    ],
)
def test_the_target_checks_unused_parameters_that_can_hold_references(kind):
    block = ir.Block(argtypes=(types.Any, kind))
    none = py.Constant(None)
    block.stmts.extend([none, func.Return(none.result)])
    code = func.Function(
        sym_name="unused",
        body=ir.Region(block),
        signature=func.Signature(inputs=(kind,), output=types.NoneType),
    )
    method = ir.Method(dialects=squin.kernel, code=code)
    assert "block argument" in ConversionTarget.check(method)
