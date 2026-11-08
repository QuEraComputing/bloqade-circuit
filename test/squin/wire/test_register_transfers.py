"""Check transfers that fill taken register ranges with different group sizes."""

import pytest
from kirin import ir, types
from kirin.dialects import py, func
from kirin.ir.exception import ValidationErrorGroup

from bloqade.squin.wire import stmts, kernel
from bloqade.squin.analysis.validation.wire import WireValidation


def transfers(*, take_slice: bool, positions: tuple[int, ...]) -> ir.Method:
    """Move three wires out of a register and put them into the requested positions."""
    block = ir.Block(argtypes=(types.Any,))
    indices = [py.Constant(index) for index in range(5)]
    block.stmts.extend(indices)
    allocation = stmts.AllocRegister(indices[4].result)
    block.stmts.append(allocation)
    register = allocation.result
    if take_slice:
        sliced = stmts.TakeSlice(register, indices[0].result, indices[3].result)
        block.stmts.append(sliced)
        register = sliced.slice_register
    wires = []
    for index in range(3):
        take = stmts.Take(register, indices[index].result)
        block.stmts.append(take)
        register = take.register_out
        wires.append(take.wire)
    if take_slice:
        block.stmts.append(stmts.DiscardRegister(register))
        register = sliced.register_out
        for wire, position in zip(wires, positions, strict=True):
            put = stmts.Put(register, indices[position].result, wire)
            block.stmts.append(put)
            register = put.register_out
    else:
        packed = stmts.PackRegister(tuple(wires))
        put = stmts.PutSlice(register, indices[positions[0]].result, packed.result)
        block.stmts.extend([packed, put])
        register = put.register_out
    block.stmts.extend([stmts.FreeRegister(register), func.Return(indices[0].result)])
    return ir.Method(
        dialects=kernel,
        code=func.Function(
            sym_name="transfers",
            body=ir.Region(block),
            signature=func.Signature(inputs=(), output=types.Int),
        ),
    )


@pytest.mark.parametrize("positions", [(0, 1, 2), (1, 0, 2), (2, 1, 0)])
def test_individual_puts_fill_a_taken_slice(positions):
    WireValidation().check(transfers(take_slice=True, positions=positions))


def test_a_slice_put_fills_individually_taken_elements():
    WireValidation().check(transfers(take_slice=False, positions=(0,)))


@pytest.mark.parametrize("positions", [(0, 1, 1), (0, 1, 3)])
def test_individual_puts_cannot_replace_a_filled_element(positions):
    with pytest.raises(ValidationErrorGroup, match="requires a taken element"):
        WireValidation().check(transfers(take_slice=True, positions=positions))


def test_a_slice_put_cannot_cover_an_element_that_still_holds_a_qubit():
    with pytest.raises(ValidationErrorGroup, match="must fill a taken range"):
        WireValidation().check(transfers(take_slice=False, positions=(1,)))


def borrowed_transfer(
    *, slice_transfer: bool, replace_wire: bool, wrong_release: bool
) -> ir.Method:
    """Keep two borrows open while replacing the element between them."""
    block = ir.Block(argtypes=(types.Any,))
    indices = [py.Constant(index) for index in range(4)]
    block.stmts.extend(indices)
    zero, one, two, three = (node.result for node in indices)
    allocation = stmts.AllocRegister(three)
    first = stmts.Borrow(allocation.result, zero)
    last = stmts.Borrow(first.register_out, two)
    block.stmts.extend([allocation, first, last])
    if slice_transfer:
        take = stmts.TakeSlice(last.register_out, one, one)
        block.stmts.append(take)
        replacement = take.slice_register
        if replace_wire:
            fresh = stmts.AllocRegister(one)
            block.stmts.extend([stmts.FreeRegister(replacement), fresh])
            replacement = fresh.result
        put = stmts.PutSlice(take.register_out, one, replacement)
    else:
        take = stmts.Take(last.register_out, one)
        block.stmts.append(take)
        replacement = take.wire
        if replace_wire:
            fresh = stmts.Alloc()
            block.stmts.extend([stmts.Free(replacement), fresh])
            replacement = fresh.result
        put = stmts.Put(take.register_out, one, replacement)
    release_first = stmts.Release(
        put.register_out, zero, last.wire if wrong_release else first.wire
    )
    release_last = stmts.Release(
        release_first.register_out, two, first.wire if wrong_release else last.wire
    )
    block.stmts.extend(
        [
            put,
            release_first,
            release_last,
            stmts.FreeRegister(release_last.register_out),
            func.Return(zero),
        ]
    )
    return ir.Method(
        dialects=kernel,
        code=func.Function(
            sym_name="borrowed_transfer",
            body=ir.Region(block),
            signature=func.Signature(inputs=(), output=types.Int),
        ),
    )


@pytest.mark.parametrize("slice_transfer", [False, True])
@pytest.mark.parametrize("replace_wire", [False, True])
def test_independent_transfers_preserve_outstanding_borrows(
    slice_transfer, replace_wire
):
    WireValidation().check(
        borrowed_transfer(
            slice_transfer=slice_transfer,
            replace_wire=replace_wire,
            wrong_release=False,
        )
    )


@pytest.mark.parametrize("slice_transfer", [False, True])
@pytest.mark.parametrize("replace_wire", [False, True])
def test_independent_transfers_still_reject_swapped_releases(
    slice_transfer, replace_wire
):
    with pytest.raises(
        ValidationErrorGroup, match="put back the qubit of its register element"
    ):
        WireValidation().check(
            borrowed_transfer(
                slice_transfer=slice_transfer,
                replace_wire=replace_wire,
                wrong_release=True,
            )
        )


@pytest.mark.parametrize("swapped", [False, True])
def test_packing_preserves_each_borrowed_wires_origin(swapped):
    method = borrowed_transfer(
        slice_transfer=False, replace_wire=False, wrong_release=False
    )
    borrows = [node for node in method.code.walk() if isinstance(node, stmts.Borrow)]
    releases = [node for node in method.code.walk() if isinstance(node, stmts.Release)]
    packed = stmts.PackRegister(tuple(node.wire for node in borrows))
    packed.insert_before(releases[0])
    current = packed.result
    for position, release in enumerate(releases):
        index = py.Constant(1 - position if swapped else position)
        index.insert_before(releases[0])
        taken = stmts.Take(current, index.result)
        taken.insert_before(releases[0])
        current = taken.register_out
        release.wire = taken.wire
    stmts.DiscardRegister(current).insert_before(releases[0])
    if swapped:
        with pytest.raises(
            ValidationErrorGroup, match="put back the qubit of its register element"
        ):
            WireValidation().check(method)
    else:
        WireValidation().check(method)
