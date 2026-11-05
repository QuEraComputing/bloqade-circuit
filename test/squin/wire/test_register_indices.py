"""Check register transfer bounds and negative indices through conversion."""

import pytest
from kirin import ir, types
from kirin.dialects import py, func
from kirin.ir.exception import ValidationErrorGroup

from bloqade.pyqrack import DynamicMemorySimulator
from bloqade.squin.wire import stmts, kernel
from bloqade.squin.wire.typeinfer import InferWireTypes
from bloqade.squin.passes.wire_to_squin import WireToSquin
from bloqade.squin.analysis.validation.wire import WireValidation


def constant(block: ir.Block, value: int) -> ir.SSAValue:
    """Append an integer constant and return its result."""
    node = py.Constant(value)
    block.stmts.append(node)
    return node.result


def method(block: ir.Block) -> ir.Method:
    """Build a wire method and infer its result types."""
    result = ir.Method(
        dialects=kernel,
        code=func.Function(
            sym_name="transfer",
            body=ir.Region(block),
            signature=func.Signature(
                inputs=tuple(arg.type for arg in block.args[1:]), output=types.Any
            ),
        ),
    )
    InferWireTypes(kernel)(result)
    return result


def transfer(index: int | None, size: int | None = None) -> ir.Method:
    """Take an element or a slice and return the lengths after replacement.

    A None index reads the position from a function argument.
    A None size selects an element transfer.
    """
    block = ir.Block(
        argtypes=(types.Any,) if index is not None else (types.Any, types.Int)
    )
    allocation = stmts.AllocRegister(constant(block, 3))
    block.stmts.append(allocation)
    at = constant(block, index) if index is not None else block.args[1]
    if size is None:
        taken = stmts.Take(allocation.result, at)
        put = stmts.Put(taken.register_out, at, taken.wire)
        block.stmts.extend([taken, put])
    else:
        count = constant(block, size)
        taken = stmts.TakeSlice(allocation.result, at, count)
        length = stmts.Length(taken.slice_register)
        fresh = stmts.AllocRegister(count)
        put = stmts.PutSlice(taken.register_out, at, fresh.result)
        block.stmts.extend(
            [taken, length, stmts.FreeRegister(length.register_out), fresh, put]
        )
    total = stmts.Length(put.register_out)
    block.stmts.extend([total, stmts.FreeRegister(total.register_out)])
    if size is None:
        returned = total.result
    else:
        values = py.tuple.New((length.result, total.result))
        block.stmts.append(values)
        returned = values.result
    block.stmts.append(func.Return(returned))
    return method(block)


@pytest.mark.parametrize("index", [-3, -1, 0, 2])
@pytest.mark.parametrize("dynamic", [False, True])
def test_element_replacement_preserves_length(index, dynamic):
    restored = WireToSquin().emit(transfer(None if dynamic else index))
    args = (index,) if dynamic else ()
    assert DynamicMemorySimulator().run(restored, args=args) == 3


@pytest.mark.parametrize(
    "index, size", [(-3, 1), (-2, 2), (-1, 1), (0, 2), (2, 1), (3, 0)]
)
@pytest.mark.parametrize("dynamic", [False, True])
def test_slice_replacement_preserves_both_lengths(index, size, dynamic):
    restored = WireToSquin().emit(transfer(None if dynamic else index, size))
    args = (index,) if dynamic else ()
    assert DynamicMemorySimulator().run(restored, args=args) == (size, 3)


@pytest.mark.parametrize("index", [-4, 3, 5])
@pytest.mark.parametrize("borrow", [False, True])
def test_element_transfers_reject_known_invalid_indices(index, borrow):
    block = ir.Block(argtypes=(types.Any,))
    allocation = stmts.AllocRegister(constant(block, 3))
    block.stmts.append(allocation)
    at = constant(block, index)
    taken = (stmts.Borrow if borrow else stmts.Take)(allocation.result, at)
    block.stmts.append(taken)
    if borrow:
        release = stmts.Release(taken.register_out, at, taken.wire)
        block.stmts.extend([release, stmts.FreeRegister(release.register_out)])
    else:
        block.stmts.extend(
            [stmts.Free(taken.wire), stmts.DiscardRegister(taken.register_out)]
        )
    block.stmts.append(func.Return(constant(block, 0)))
    with pytest.raises(ValidationErrorGroup, match="within the register bounds"):
        WireValidation().check(method(block))


@pytest.mark.parametrize(
    "index, size", [(-4, 1), (2, 2), (3, 1), (5, 2), (0, -1), (4, 0)]
)
def test_slice_transfers_reject_known_invalid_ranges(index, size):
    with pytest.raises(ValidationErrorGroup, match="within the register bounds"):
        WireValidation().check(transfer(index, size))
