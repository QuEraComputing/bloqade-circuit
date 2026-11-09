"""Check register lengths and release positions across loop iterations."""

import pytest
from kirin import ir, types
from kirin.passes import TypeInfer
from kirin.dialects import py, scf, func, ilist
from kirin.ir.exception import ValidationErrorGroup

from bloqade.squin.wire import RegisterType, stmts, kernel
from bloqade.squin.wire.returns import ReturnPolicy, set_return_policy
from bloqade.squin.analysis.validation.wire import WireValidation
from bloqade.squin.analysis.validation.wire.registers import RegisterAnalysis


def constant(block: ir.Block, value: int) -> ir.SSAValue:
    """Append an integer constant to the block and return its result."""
    node = py.Constant(value)
    block.stmts.append(node)
    return node.result


def growing_register(*, grow: bool, release_last: bool) -> ir.Method:
    """Build a loop that borrows the last element and optionally grows its register."""
    top = ir.Block(argtypes=(types.Any,))
    allocation = stmts.AllocRegister(constant(top, 2))
    iterable = py.Constant(ilist.IList(range(3)))
    top.stmts.extend([allocation, iterable])
    body = ir.Block(argtypes=(types.Int, RegisterType))
    one = constant(body, 1)
    length = stmts.Length(body.args[1])
    last = py.Sub(length.result, one)
    last.result.type = types.Int
    borrow = stmts.Borrow(length.register_out, last.result)
    release = stmts.Release(
        borrow.register_out, last.result if release_last else one, borrow.wire
    )
    body.stmts.extend([length, last, borrow, release])
    result = release.register_out
    if grow:
        fresh = stmts.Alloc()
        packed = stmts.PackRegister((fresh.result,))
        joined = stmts.JoinRegister(result, packed.result)
        body.stmts.extend([fresh, packed, joined])
        result = joined.result
    body.stmts.append(scf.Yield(result))
    loop = scf.For(iterable.result, ir.Region(body), allocation.result)
    top.stmts.extend([loop, stmts.FreeRegister(loop.results[0])])
    top.stmts.append(func.Return(constant(top, 0)))
    method = ir.Method(
        dialects=kernel,
        code=func.Function(
            sym_name="growing_register",
            body=ir.Region(top),
            signature=func.Signature(inputs=(), output=types.Int),
        ),
    )
    set_return_policy(method, ReturnPolicy.ExplicitReturns)
    return method


@pytest.mark.parametrize(
    "grow, release_last", [(False, False), (False, True), (True, True)]
)
def test_loop_releases_the_borrowed_element(grow, release_last):
    WireValidation().check(growing_register(grow=grow, release_last=release_last))


def test_loop_rejects_a_release_that_fails_after_register_growth():
    method = growing_register(grow=True, release_last=False)
    with pytest.raises(ValidationErrorGroup, match="register element"):
        WireValidation().check(method)


def test_loop_validation_reports_exhaustion_before_accepting_unstable_facts():
    method = growing_register(grow=True, release_last=True)
    analysis = RegisterAnalysis(method.dialects, max_loop_iterations=1)
    analysis.run(method)
    assert any(
        "did not converge within 1 iterations" in str(error)
        for error in analysis.get_validation_errors()
    )


def split_register(index: int, *, relative: bool = False) -> ir.Method:
    """Build a split at a constant index or at the register length plus that index."""
    top = ir.Block(argtypes=(types.Any,))
    allocation = stmts.AllocRegister(constant(top, 3))
    top.stmts.append(allocation)
    register = allocation.result
    at = constant(top, index)
    if relative:
        length = stmts.Length(register)
        offset = py.Add(length.result, at)
        offset.result.type = types.Int
        top.stmts.extend([length, offset])
        register, at = length.register_out, offset.result
    split = stmts.SplitRegister(register, at)
    top.stmts.append(split)
    top.stmts.extend(stmts.FreeRegister(part) for part in split.results)
    top.stmts.append(func.Return(constant(top, 0)))
    return ir.Method(
        dialects=kernel,
        code=func.Function(
            sym_name="split_register",
            body=ir.Region(top),
            signature=func.Signature(inputs=(), output=types.Int),
        ),
    )


@pytest.mark.parametrize("index", [0, 1, 3])
def test_split_accepts_indices_within_the_register(index):
    method = split_register(index)
    TypeInfer(method.dialects)(method)
    WireValidation().check(method)


@pytest.mark.parametrize(
    "index, relative", [(-1, False), (4, False), (5, False), (1, True)]
)
@pytest.mark.parametrize("infer", [False, True])
def test_split_rejects_indices_outside_the_register(index, relative, infer):
    method = split_register(index, relative=relative)
    if infer:
        TypeInfer(method.dialects)(method)
    with pytest.raises(ValidationErrorGroup, match="split index"):
        WireValidation().check(method)
