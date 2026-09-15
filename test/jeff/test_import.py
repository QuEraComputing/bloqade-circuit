"""Importing jeff-format modules into dialect IR, and the errors raised for
inputs the dialect cannot model."""

import pytest
from kirin import types, lowering
from kirin.ir.exception import ValidationErrorGroup

import jeff as jf
from bloqade import jeff
from bloqade.jeff import JeffImportError, emit_jeff, load_jeff
from bloqade.jeff.types import IntArrayType
from bloqade.jeff.dialects import stmts
from bloqade.jeff.parse.lowering import JeffLowering

from . import test_roundtrip as tr
from .build import add, entry, method, validate


def _module(operations, sources=(), targets=(), name="f"):
    body = jf.JeffRegion(
        sources=list(sources), targets=list(targets), operations=list(operations)
    )
    module = jf.JeffModule([jf.FunctionDef(name=name, body=body)])
    module.refresh()
    return module


def test_imported_module_verifies_and_reemits():
    element = jf.JeffOp("int", "const32", [], [jf.JeffValue(jf.IntType(32))], 7)
    created = jf.JeffOp(
        "intArray",
        "create",
        [element.outputs[0]],
        [jf.JeffValue(jf.IntArrayType(32, 1))],
    )
    method = load_jeff(_module([element, created], targets=[created.outputs[0]]))
    validate(method)
    assert "intArray.create" in str(emit_jeff(method))


def test_select_reemits_as_a_switch():
    """MQT Core exports `select`; jeff-format 0.1 reads it but cannot
    encode it, so it is re-emitted as the switch it is."""
    flag = jf.JeffValue(jf.IntType(1))  # an input, so nothing folds the choice
    one = jf.JeffOp("int", "const32", [], [jf.JeffValue(jf.IntType(32))], 1)
    two = jf.JeffOp("int", "const32", [], [jf.JeffValue(jf.IntType(32))], 2)
    picked = jf.JeffOp(
        "int",
        "select",
        [flag, one.outputs[0], two.outputs[0]],
        [jf.JeffValue(jf.IntType(32))],
    )
    try:
        module = _module(
            [one, two, picked], sources=[flag], targets=[picked.outputs[0]]
        )
    except AttributeError:  # the released schema cannot encode a select
        pytest.skip("this jeff-format schema has no select")
    method = load_jeff(module)
    assert any(isinstance(n, stmts.IntSelect) for n in method.callable_region.walk())
    assert "switch" in [op.subkind for op in emit_jeff(method)[0].body.operations]


def test_negative_array_constants_round_trip():
    """Arrays store bit patterns as scalars do."""
    block, _ = entry()
    array = add(block, stmts.IntArrayConst(values=(-1, 7), bitwidth=32)).result
    module = emit_jeff(method(block, array, IntArrayType))
    (const,) = [
        n
        for n in load_jeff(module).callable_region.walk()
        if isinstance(n, stmts.IntArrayConst)
    ]
    assert const.values == (-1, 7)


def test_rejects_int64():
    """The dialect's integers are 32-bit patterns; a wider integer would be
    silently narrowed, so it is refused."""
    value = jf.JeffOp("int", "const64", [], [jf.JeffValue(jf.IntType(64))], 5)
    with pytest.raises(JeffImportError, match="unsupported value type: int64"):
        load_jeff(_module([value], targets=[value.outputs[0]]))


def test_rejects_body_less_declaration():
    module = jf.JeffModule([jf.FunctionDecl(name="external", inputs=[], outputs=[])])
    with pytest.raises(JeffImportError, match="declaration"):
        load_jeff(module)


def test_rejects_a_value_used_before_it_is_defined():
    """jeff orders operations by definition; a cycle is the same fault."""
    a_val = jf.JeffValue(jf.IntType(32))
    b_val = jf.JeffValue(jf.IntType(32))
    a = jf.JeffOp("int", "not", [a_val], [b_val])
    b = jf.JeffOp("int", "not", [b_val], [a_val])
    module = jf.JeffModule(
        [
            jf.FunctionDef(
                name="cycle",
                body=jf.JeffRegion(sources=[], targets=[], operations=[a, b]),
            )
        ]
    )
    module.refresh()
    with pytest.raises(JeffImportError, match="used before it is defined"):
        load_jeff(module)


def test_rejects_a_value_produced_twice():
    first = jf.JeffOp("int", "const32", [], [jf.JeffValue(jf.IntType(32))], 1)
    second = jf.JeffOp("int", "const32", [], list(first.outputs), 2)
    with pytest.raises(JeffImportError, match="produced twice"):
        load_jeff(_module([first, second], targets=list(first.outputs)))


def test_rejects_unsupported_float_bitwidth():
    value = jf.JeffValue(jf.FloatType(32))
    module = _module([], sources=[value], targets=[value], name="f32")
    with pytest.raises(JeffImportError, match="unsupported value type: float"):
        load_jeff(module)


def test_rejects_switch_without_default():
    selector = jf.JeffOp("int", "const1", [], [jf.JeffValue(jf.IntType(1))], True)
    switch = jf.JeffOp(
        "scf",
        "switch",
        [selector.outputs[0]],
        [],
        instruction_data=jf.SwitchSCF(
            branches=[jf.JeffRegion(sources=[], targets=[], operations=[])]
        ),
    )
    with pytest.raises(JeffImportError, match="default"):
        load_jeff(_module([selector, switch]))


def _op(kind, subkind, *outputs, inputs=(), data=None):
    return jf.JeffOp(kind, subkind, list(inputs), list(outputs), data)


def _unrefreshed(operations, sources=(), targets=()):
    """A module whose values carry ids but that the encoder never validated.

    The encoder rejects kinds and subkinds outside the schema, so the
    loader's own refusals of them are reached with such a module.
    """
    module = jf.JeffModule(
        [
            jf.FunctionDef(
                name="f",
                body=jf.JeffRegion(
                    sources=list(sources),
                    targets=list(targets),
                    operations=list(operations),
                ),
            )
        ]
    )
    values = [*sources, *(value for op in operations for value in op.outputs)]
    for index, value in enumerate(values):
        value._val_idx = index  # the id an encoding would assign
    return module


@pytest.mark.parametrize(
    "operation, message",
    [
        (_op("qubit", "bogus", jf.JeffValue(jf.QubitType())), "unsupported qubit op"),
        (_op("qureg", "bogus", jf.JeffValue(jf.QuregType(2))), "unsupported qureg op"),
        (_op("int", "bogus", jf.JeffValue(jf.IntType(32))), "unsupported int op"),
        (
            _op("intArray", "bogus", jf.JeffValue(jf.IntArrayType(32, 1))),
            "unsupported intArray op",
        ),
        (_op("bogus", "x", jf.JeffValue(jf.IntType(32))), "unsupported operation kind"),
        (_op("qubit", "alloc"), "has 0 outputs. The statement expects 1."),
        (
            _op("int", "const32", jf.JeffValue("weird"), data=7),
            "unsupported value type",
        ),
        (
            _op("int", "const32", jf.JeffValue(jf.IntType(32)), data="seven"),
            "malformed jeff module",
        ),
        (_op("scf", "for", data="nope"), "unsupported scf form"),
        (
            _op("float", "const64", jf.JeffValue(jf.FloatType(64)), data="x"),
            "malformed jeff module",
        ),
    ],
    ids=lambda x: x if isinstance(x, str) else f"{x.kind}.{x.subkind}",
)
def test_rejects_operations_the_dialect_does_not_model(operation, message):
    with pytest.raises(JeffImportError, match=message):
        load_jeff(_unrefreshed([operation], targets=list(operation.outputs)))


def test_rejects_a_gate_of_unknown_form():
    q = _op("qubit", "alloc", jf.JeffValue(jf.QubitType()))
    gate = _op(
        "qubit", "gate", jf.JeffValue(jf.QubitType()), inputs=q.outputs, data="nope"
    )
    with pytest.raises(JeffImportError, match="unsupported gate form"):
        load_jeff(_unrefreshed([q, gate], targets=gate.outputs))


def test_a_callee_called_twice_is_imported_once():
    callee_block, _ = entry()
    w = add(callee_block, stmts.Alloc()).result
    m = add(callee_block, stmts.MeasureNd(w))
    add(callee_block, stmts.Free(m.result_wire))
    callee = method(callee_block, m.bit, types.Bool, name="flip")
    block, _ = entry()
    first = add(block, stmts.Call(callee, (), (types.Bool,))).results[0]
    second = add(block, stmts.Call(callee, (), (types.Bool,))).results[0]
    mt = method(block, (first, second), types.Generic(tuple, types.Bool, types.Bool))
    module = emit_jeff(mt)
    assert len(module.functions) == 2
    reloaded = load_jeff(module)
    calls = [n for n in reloaded.callable_region.walk() if isinstance(n, stmts.Call)]
    assert calls[0].callee.code is calls[1].callee.code


def test_the_validation_refuses_an_array_read_that_produces_no_integer():
    array = jf.JeffValue(jf.IntArrayType(32, 1))
    index = jf.JeffValue(jf.IntType(32))
    read = _op(
        "intArray", "getIndex", jf.JeffValue(jf.FloatType(64)), inputs=(array, index)
    )
    with pytest.raises(ValidationErrorGroup, match="Invalid type"):
        load_jeff(_unrefreshed([read], sources=(array, index), targets=read.outputs))


def test_the_lowering_runs_on_one_function_definition():
    module = emit_jeff(tr.bell())
    lowered = JeffLowering(jeff.kernel, module=module)
    region = lowered.run(module[module.entrypoint])
    assert isinstance(region.blocks[0].last_stmt, stmts.Return)
    assert not lowered.methods  # `run` records no method.


def test_the_lowering_refuses_nodes_that_it_cannot_lower():
    module = emit_jeff(tr.bell())
    function = module[module.entrypoint]
    lowered = JeffLowering(jeff.kernel, module=module)
    state = lowering.State(lowered)
    with pytest.raises(JeffImportError, match="starts at a function definition"):
        lowered.run(function.body.operations[0])
    with pytest.raises(JeffImportError, match="no literal values"):
        lowered.lower_literal(state, 1)
    with pytest.raises(JeffImportError, match="only a call operation"):
        lowered.lower_global(state, function.body.operations[0])
    with pytest.raises(JeffImportError, match="is no operation"):
        lowered.visit(state, function)
