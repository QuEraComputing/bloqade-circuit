"""Check register restoration through dynamic indices and function boundaries."""

import pytest
from kirin import ir, types
from kirin.dialects import py, func
from test_validation import errors

from bloqade.squin.wire import RegisterType, stmts, kernel
from bloqade.squin.analysis.validation.wire import (
    WireValidation,
    BorrowValidation,
    PositionValidation,
    LinearityValidation,
    StructureValidation,
)


def register_method(
    *, leak: bool = False, mismatched: bool = False, packed: bool = False
) -> ir.Method:
    """Build a register round trip whose release uses an equivalent index expression."""
    block = ir.Block()
    block.args.append_from(types.Any, "self")
    register = block.args.append_from(RegisterType, "register")
    i = block.args.append_from(types.Int, "i")
    j = block.args.append_from(types.Int, "j")
    zero = py.Constant(0)
    equivalent = py.Add(i, zero.result)
    equivalent.result.type = types.Int
    first = stmts.Borrow(register, i)
    released = stmts.Release(
        first.register_out, j if mismatched else equivalent.result, first.wire
    )
    block.stmts.extend([zero, equivalent, first, released])
    result = released.register_out
    if leak:
        second = stmts.Borrow(result, i)
        block.stmts.extend([second, stmts.Free(second.wire)])
        result = second.register_out
    if packed:
        pair = py.tuple.New((zero.result, result))
        block.stmts.append(pair)
        result = pair.result
    block.stmts.append(func.Return(result))
    code = func.Function(
        sym_name="register_method",
        body=ir.Region(block),
        signature=func.Signature(
            inputs=(RegisterType, types.Int, types.Int), output=result.type
        ),
    )
    return ir.Method(dialects=kernel, code=code)


@pytest.mark.parametrize("packed", [False, True])
def test_equivalent_indices_restore_the_register(packed):
    WireValidation().check(register_method(packed=packed))


@pytest.mark.parametrize("packed", [False, True])
def test_a_later_borrow_cannot_escape_after_an_equivalent_index_release(packed):
    method = register_method(leak=True, packed=packed)
    for check in (StructureValidation(), LinearityValidation(), PositionValidation()):
        assert errors(check, method) == []
    assert errors(BorrowValidation(), method)


def test_a_symbolic_release_requires_a_matching_borrow():
    assert errors(BorrowValidation(), register_method(mismatched=True))
