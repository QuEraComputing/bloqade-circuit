"""Check return policies without changing function attributes or callee policies."""

import pytest
from kirin import ir, types
from kirin.dialects import py, func

from bloqade.squin.wire import WireType, kernel
from bloqade.squin.wire.returns import ReturnPolicy, set_return_policy
from bloqade.squin.analysis.validation.wire import RegisterValidation


def pair_method(*, exchange: bool) -> ir.Method:
    """Build a function that returns its wire arguments in either order."""
    block = ir.Block(argtypes=(types.Any, WireType, WireType))
    wires = tuple(block.args[1:])
    result = py.tuple.New(wires[::-1] if exchange else wires)
    block.stmts.extend([result, func.Return(result.result)])
    return ir.Method(
        dialects=kernel,
        code=func.Function(
            sym_name="pair",
            body=ir.Region(block),
            signature=func.Signature(
                inputs=(WireType, WireType),
                output=types.Generic(tuple, WireType, WireType),
            ),
        ),
    )


@pytest.mark.parametrize("exchange", [False, True])
def test_policy_override_checks_positions_without_changing_attributes(
    exchange: bool,
) -> None:
    method = pair_method(exchange=exchange)
    set_return_policy(method, ReturnPolicy.ExplicitReturns)
    before = dict(method.code.attributes)
    assert RegisterValidation().run(method)[1] == []
    _, errors = RegisterValidation(return_policy=ReturnPolicy.PreserveArguments).run(
        method
    )
    assert bool(errors) == exchange
    assert method.code.attributes == before
    assert RegisterValidation().run(method)[1] == []


@pytest.mark.parametrize("callee_policy", list(ReturnPolicy))
def test_root_policy_override_keeps_the_callee_policy(
    callee_policy: ReturnPolicy,
) -> None:
    callee = pair_method(exchange=True)
    set_return_policy(callee, callee_policy)
    caller = pair_method(exchange=False)
    block = caller.callable_region.blocks[0]
    packed = block.stmts.at(0)
    call = func.Invoke(tuple(block.args[1:]), callee=callee)
    call.insert_before(packed)
    restored: list[ir.SSAValue] = []
    for position in (1, 0):
        index = py.Constant(position)
        index.insert_before(packed)
        item = py.GetItem(call.result, index.result)
        item.result.type = WireType
        item.insert_before(packed)
        restored.append(item.result)
    packed.args = tuple(restored)
    set_return_policy(caller, ReturnPolicy.ExplicitReturns)
    before = dict(callee.code.attributes)
    _, errors = RegisterValidation(return_policy=ReturnPolicy.PreserveArguments).run(
        caller
    )
    assert bool(errors) == (callee_policy is ReturnPolicy.PreserveArguments)
    assert callee.code.attributes == before
