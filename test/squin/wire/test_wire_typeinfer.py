"""Check register length inference at calls and its boundary validation."""

import pytest
from kirin import ir, types
from kirin.dialects import py, func
from kirin.ir.exception import ValidationErrorGroup

from bloqade.squin.wire import RegisterType, stmts, kernel, register_type
from bloqade.squin.wire.returns import ReturnPolicy, set_return_policy
from bloqade.squin.wire.typeinfer import InferWireTypes
from bloqade.squin.analysis.validation.wire import WireValidation


def register_call(*, explicit_returns: bool) -> tuple[ir.Method, func.Invoke]:
    """Build a call that preserves its register or consumes the first qubit."""
    body = ir.Block(argtypes=(types.Any, RegisterType))
    output = body.args[1]
    if explicit_returns:
        one = py.Constant(1)
        split = stmts.SplitRegister(output, one.result)
        body.stmts.extend([one, split, stmts.FreeRegister(split.before)])
        output = split.after
    body.stmts.append(func.Return(output))
    callee = ir.Method(
        dialects=kernel,
        code=func.Function(
            sym_name="callee",
            body=ir.Region(body),
            signature=func.Signature(inputs=(RegisterType,), output=RegisterType),
        ),
    )
    if explicit_returns:
        set_return_policy(callee, ReturnPolicy.ExplicitReturns)
    InferWireTypes(kernel)(callee)
    WireValidation().check(callee)
    block = ir.Block(argtypes=(types.Any,))
    three, zero = py.Constant(3), py.Constant(0)
    allocation = stmts.AllocRegister(three.result)
    call = func.Invoke((allocation.result,), callee=callee)
    block.stmts.extend(
        [
            three,
            zero,
            allocation,
            call,
            stmts.FreeRegister(call.result),
            func.Return(zero.result),
        ]
    )
    caller = ir.Method(
        dialects=kernel,
        code=func.Function(
            sym_name="caller",
            body=ir.Region(block),
            signature=func.Signature(inputs=(), output=types.Int),
        ),
    )
    return caller, call


@pytest.mark.parametrize("explicit_returns", [False, True])
def test_call_length_refinement_respects_the_return_policy(explicit_returns):
    caller, call = register_call(explicit_returns=explicit_returns)
    InferWireTypes(kernel)(caller)
    expected = RegisterType if explicit_returns else register_type(3)
    assert call.result.type == expected
    WireValidation().check(caller)


@pytest.mark.parametrize("explicit_returns", [False, True])
def test_call_validation_rejects_a_length_that_the_contract_does_not_preserve(
    explicit_returns,
):
    caller, call = register_call(explicit_returns=explicit_returns)
    InferWireTypes(kernel)(caller)
    call.result.type = register_type(4)
    with pytest.raises(ValidationErrorGroup, match="call result must preserve"):
        WireValidation().check(caller)
