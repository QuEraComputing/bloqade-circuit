"""Check allocation lifetimes and current wire values across structured regions."""

import pytest
from kirin import ir
from kirin.dialects import py, scf, func
from test_roundtrip import ladder, simulate
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.qubit import qalloc
from bloqade.constants import constant_int
from bloqade.squin.wire import GateKind, WireConversionError, stmts
from bloqade.squin.emit.wire import EmitWire
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin
from bloqade.squin.analysis.validation.wire import WireValidation


def snapshot(method):
    """Record the program and every SSA use without changing either."""
    values = {
        value for node in method.code.walk() for value in (*node.args, *node.results)
    }
    return method.code.print_str(), {value: frozenset(value.uses) for value in values}


def test_conversion_preserves_the_program_and_its_use_lists():
    before = snapshot(ladder)
    method = SquinToWire().emit(ladder)
    assert snapshot(ladder) == before
    WireValidation().check(method)
    assert simulate(WireToSquin().emit(method)) == [1, 1, 1, 1]


def test_wire_validation_rejects_a_duplicate_borrow():
    method = SquinToWire().emit(ladder)
    first = next(node for node in method.code.walk() if isinstance(node, stmts.Borrow))
    uses = tuple(first.register_out.uses)
    duplicate = stmts.Borrow(first.register_out, first.index)
    duplicate.insert_after(first)
    for use in uses:
        args = list(use.stmt.args)
        args[use.index] = duplicate.register_out
        use.stmt.args = tuple(args)
    with pytest.raises(ValidationErrorGroup, match="already borrowed"):
        WireValidation().check(method)


@squin.kernel
def branch_then_loop(flag: bool, n: int):
    qs = squin.qalloc(2)
    if flag:
        squin.x(qs[0])
    else:
        squin.x(qs[1])
    for _ in range(n):
        squin.x(qs[0])
    return squin.broadcast.measure(qs)


@pytest.mark.parametrize("flag", [False, True])
@pytest.mark.parametrize("n", [0, 1, 2])
def test_branches_start_from_the_same_values_and_loops_continue_the_selected_branch(
    flag, n
):
    wired = SquinToWire().emit(branch_then_loop)
    assert simulate(WireToSquin().emit(wired), flag, n) == [
        (int(flag) + n) % 2,
        int(not flag),
    ]


@squin.kernel
def index_from_branch(flag: bool):
    qs = squin.qalloc(3)
    if flag:
        squin.x(qs[0])
        index = 1
    else:
        squin.x(qs[0])
        index = 2
    squin.x(qs[index])
    return squin.broadcast.measure(qs)


@pytest.mark.parametrize("flag", [False, True])
def test_index_materialization_uses_the_rebuilt_branch_result(flag):
    wired = SquinToWire().emit(index_from_branch)
    assert simulate(WireToSquin().emit(wired), flag) == [1, int(flag), int(not flag)]


@squin.kernel
def allocation_order():
    a = squin.qubit.new()
    b = squin.qubit.new()
    squin.x(b)
    squin.z(a)


def gate_kind(node):
    """Return the kind of a wire gate, or None for any other statement."""
    return node.kind if isinstance(node, stmts.Gate) else None


def test_allocations_keep_source_order_and_live_until_the_block_exit():
    method = SquinToWire().emit(allocation_order)
    nodes = list(method.callable_region.blocks[0].stmts)
    first, second = [node for node in nodes if isinstance(node, stmts.Alloc)]
    x = next(node for node in nodes if gate_kind(node) is GateKind.X)
    z = next(node for node in nodes if gate_kind(node) is GateKind.Z)
    assert x.args[0] is second.result
    assert z.args[0] is first.result
    assert nodes.index(first) < nodes.index(second) < nodes.index(x) < nodes.index(z)
    frees = [node for node in nodes if isinstance(node, stmts.Free)]
    assert len(frees) == 2
    assert all(nodes.index(free) > nodes.index(z) for free in frees)
    assert isinstance(nodes[-1], func.Return)


@squin.kernel
def unused_allocation():
    squin.qalloc(3)


def test_emission_preserves_an_unused_register_allocation():
    method = SquinToWire().emit(unused_allocation)
    nodes = list(method.callable_region.blocks[0].stmts)
    allocation = next(node for node in nodes if isinstance(node, stmts.AllocRegister))
    release = next(node for node in nodes if isinstance(node, stmts.FreeRegister))
    assert constant_int(allocation.size) == 3
    assert release.register is allocation.result


@squin.kernel
def local_in_loop(n: int):
    for _ in range(n):
        q = squin.qubit.new()
        squin.x(q)


def test_each_iteration_owns_its_local_allocation():
    method = SquinToWire().emit(local_in_loop)
    loop = next(node for node in method.code.walk() if isinstance(node, scf.For))
    allocation = next(
        node for node in loop.body.walk() if isinstance(node, stmts.Alloc)
    )
    release = next(node for node in loop.body.walk() if isinstance(node, stmts.Free))
    assert allocation.parent_block is release.parent_block is loop.body.blocks[0]
    assert not loop.initializers


@squin.kernel
def uncertain_loop(n: int, i: int):
    a = squin.qalloc(2)
    b = squin.qalloc(1)
    for _ in range(n):
        squin.cx(a[0], a[i])
        squin.x(b[0])
    return squin.broadcast.measure(a), squin.broadcast.measure(b)


def test_emission_converts_every_allocation_before_borrow_validation():
    method = uncertain_loop.similar()
    method = EmitWire(method.dialects, method, {}).emit_method()
    allocations = [
        node for node in method.code.walk() if isinstance(node, stmts.AllocRegister)
    ]
    assert len(allocations) == 2
    assert not any(
        isinstance(node, func.Invoke) and node.callee is qalloc
        for node in method.code.walk()
    )
    WireValidation().check(method)


def test_emission_rejects_an_unsupported_reference_observer():
    method = unused_allocation.similar()
    allocation = next(
        node
        for node in method.code.walk()
        if isinstance(node, func.Invoke) and node.callee is qalloc
    )
    compare = py.cmp.Eq(allocation.result, allocation.result)
    compare.insert_after(allocation)
    with pytest.raises(WireConversionError, match="Unsupported reference operation"):
        EmitWire(method.dialects, method, {}).emit_method()


@squin.kernel
def one_captured_register(n: int):
    active = squin.qalloc(2)
    outside = squin.qalloc(1)
    for _ in range(n):
        squin.x(active[0])
        local = squin.qubit.new()
        squin.x(local)
    squin.x(outside[0])
    return squin.broadcast.measure(active), squin.broadcast.measure(outside)


@pytest.mark.parametrize("n", [0, 1, 2])
def test_a_loop_carries_available_allocations_and_preserves_unused_wires(n):
    """Carry outer allocations in source order and free local allocations inside the loop."""
    method = SquinToWire().emit(one_captured_register)
    loop = next(node for node in method.code.walk() if isinstance(node, scf.For))
    assert len(loop.initializers) == 2
    assert all(
        isinstance(value.owner, stmts.AllocRegister) for value in loop.initializers
    )
    assert [constant_int(value.owner.size) for value in loop.initializers] == [2, 1]
    end = loop.body.blocks[0].last_stmt
    assert isinstance(end, scf.Yield)
    assert end.values[-1] is loop.body.blocks[0].args[-1]
    assert len([node for node in loop.body.walk() if isinstance(node, stmts.Free)]) == 1
    assert simulate(WireToSquin().emit(method), n) == [[n % 2, 0], [1]]


def test_wire_validation_rejects_an_outstanding_borrow_at_a_boundary():
    """Require the register's complete state before passing it into a loop or branch."""
    method = SquinToWire().emit(branch_then_loop)
    release = next(
        node for node in method.code.walk() if isinstance(node, stmts.Release)
    )
    release.register_out.replace_by(release.register)
    release.delete()
    with pytest.raises(ValidationErrorGroup, match="borrowed slots"):
        WireValidation().check(method)


@pytest.mark.parametrize("kernel", [ladder, index_from_branch])
def test_conversion_resolves_references_without_a_recorded_identity_table(
    monkeypatch, kernel
):
    """Require emission to resolve source values independently of validator state."""
    from bloqade.squin.analysis.validation.wire.position import PositionAnalysis

    def forbid_table(*args, **kwargs):
        raise AssertionError("Conversion must resolve the current source definitions.")

    method = kernel.similar()
    with monkeypatch.context() as context:
        context.setattr(PositionAnalysis, "run", forbid_table)
        method = EmitWire(method.dialects, method, {}).emit_method()
    WireValidation().check(method)


@squin.kernel
def selected_element():
    qs = squin.qalloc(2)
    squin.x(qs[0])
    return squin.broadcast.measure(qs)


def test_emission_discovers_an_unused_source_allocation():
    from bloqade.qubit import stmts as qubit_stmts

    source = unused_allocation.similar()
    end = source.callable_region.blocks[0].last_stmt
    assert isinstance(end, func.Return)
    qubit_stmts.New().insert_before(end)
    method = SquinToWire().emit(source)
    nodes = list(method.callable_region.blocks[0].stmts)
    allocation = next(node for node in nodes if isinstance(node, stmts.Alloc))
    release = next(node for node in nodes if isinstance(node, stmts.Free))
    assert release.wire is allocation.result


@pytest.mark.parametrize("length", [64, 256])
def test_complete_conversion_cleans_deep_alias_chains(length):
    method = selected_element.similar()
    allocation = next(
        node
        for node in method.code.walk()
        if isinstance(node, func.Invoke) and node.callee is qalloc
    )
    uses = tuple(allocation.result.uses)
    value, after = allocation.result, allocation
    for i in range(length):
        alias = py.assign.Alias(value, target=ir.PyAttr(f"alias_{i}"))
        alias.result.type = value.type
        alias.insert_after(after)
        value, after = alias.result, alias
    for use in uses:
        args = list(use.stmt.args)
        args[use.index] = value
        use.stmt.args = tuple(args)
    before = method.code.print_str()
    wired = SquinToWire().emit(method)
    assert simulate(WireToSquin().emit(wired)) == [1, 0]
    assert not any(isinstance(node, py.assign.Alias) for node in wired.code.walk())
    assert method.code.print_str() == before


@squin.kernel
def repeated_branch_condition(flag: bool):
    qs = squin.qalloc(1)
    if flag:
        if flag:
            squin.x(qs[0])
        else:
            squin.x(qs[0])
    else:
        squin.x(qs[0])
    return squin.broadcast.measure(qs)


@pytest.mark.parametrize("flag", [False, True])
def test_stage_types_cover_both_bodies_of_repeated_conditions(flag):
    wired = SquinToWire().emit(repeated_branch_condition)
    assert simulate(WireToSquin().emit(wired), flag) == [1]
