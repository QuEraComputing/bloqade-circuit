"""Check source contracts and the types at the boundaries of emitted wire code."""

from typing import Any

import pytest
from kirin import ir, types
from kirin.source import SourceInfo
from kirin.dialects import scf, func, ilist
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.types import Qubit, holds_qubits, output_types
from bloqade.squin.wire.types import WireType, RegisterType
from bloqade.squin.wire.errors import WireConversionError
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.analysis.validation.wire import WireValidation


@squin.kernel
def borrowed_loop(q: Qubit, qs: ilist.IList[Qubit, Any], n: int):
    for i in range(n):
        squin.x(qs[i])
        squin.x(q)
    return n


def test_emitted_loop_arguments_and_borrowed_result_order():
    wired = SquinToWire().emit(borrowed_loop)
    assert isinstance(wired.code, func.Function)
    assert output_types(wired.code.signature.output) == (
        types.Int,
        WireType,
        RegisterType,
    )
    loop = next(node for node in wired.code.walk() if isinstance(node, scf.For))
    assert not any(
        holds_qubits(value.type)
        for value in (*loop.args, *loop.results, *loop.body.blocks[0].args)
    )
    assert tuple(value.type for value in loop.initializers[-2:]) == (
        WireType,
        RegisterType,
    )
    assert tuple(value.type for value in loop.body.blocks[0].args[-2:]) == (
        WireType,
        RegisterType,
    )
    end = loop.body.blocks[0].last_stmt
    assert isinstance(end, scf.Yield)
    assert tuple(value.type for value in end.values[-2:]) == (WireType, RegisterType)


def test_a_loop_body_with_a_second_block_keeps_its_source_location():
    method = borrowed_loop.similar()
    loop = next(node for node in method.code.walk() if isinstance(node, scf.For))
    loop.source = SourceInfo(17, 4, 17, 12, file="example.py")
    extra = ir.Block()
    extra.stmts.append(scf.Yield(*loop.body.blocks[0].last_stmt.args))
    loop.body.blocks.append(extra)
    # Kirin's structure check rejects the body before emission starts.
    with pytest.raises(ValidationErrorGroup, match="single block") as caught:
        SquinToWire().emit(method)
    (error,) = caught.value.errors
    assert error.node is loop
    assert loop.source.file == "example.py"
    assert loop.source.lineno == 17


def test_emitted_signature_rejects_reordered_borrowed_results():
    method = SquinToWire().emit(borrowed_loop)
    end = method.callable_region.blocks[0].last_stmt
    assert isinstance(end, func.Return)
    packed = end.value.owner
    packed.args = (packed.args[0], packed.args[2], packed.args[1])
    packed.results[0].type = types.Generic(
        tuple, *(value.type for value in packed.args)
    )
    method.code.signature = func.Signature(
        inputs=method.code.signature.inputs, output=packed.results[0].type
    )
    method.callable_region.blocks[0].args[0].type = types.MethodType[
        list(method.code.signature.inputs), packed.results[0].type
    ]
    with pytest.raises(ValidationErrorGroup, match="Return suffix position"):
        WireValidation().check(method)


@squin.kernel
def dynamic_call(gate, qs: ilist.IList[Qubit, Any]):
    gate(qs)


def test_a_call_through_a_function_value_names_the_static_call_rule():
    with pytest.raises(WireConversionError, match="static call target"):
        SquinToWire().emit(dynamic_call)
