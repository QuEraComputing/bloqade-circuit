"""Check direct wire emission through Kirin's region interpreter."""

from types import ModuleType
from typing import Any
from collections import Counter

import pytest
from kirin import types
from kirin.dialects import py, scf, func, ilist
from test_roundtrip import nested, simulate

from bloqade import squin
from bloqade.types import Qubit
from bloqade.squin.wire import WireConversionError, stmts
from bloqade.squin.emit.wire import EmitWire
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin
from bloqade.squin.analysis.validation.wire import WireValidation
from bloqade.squin.analysis.validation.wire.target import ConversionTarget


def test_emission_visits_each_source_statement_once_and_preserves_source(monkeypatch):
    source = nested
    before = source.code.print_str()
    nodes = tuple(source.code.walk())
    uses = {value: set(value.uses) for node in nodes for value in node.results}
    visits = Counter()
    evaluate = EmitWire.frame_eval

    def record(emitter, frame, node):
        visits[node] += 1
        return evaluate(emitter, frame, node)

    monkeypatch.setattr(EmitWire, "frame_eval", record)
    emitter = EmitWire(source.dialects, source, {})
    for _ in range(2):
        visits.clear()
        wired = emitter.emit_method()
        assert all(visits[node] == 1 for node in nodes)
        assert source.code.print_str() == before
        assert all(set(value.uses) == previous for value, previous in uses.items())
        assert not ConversionTarget.check(wired)
        WireValidation().check(wired)
        reconstructed = WireToSquin().emit(wired)
        assert simulate(reconstructed, 1, True) == [1, 1, 1, 0]
        assert simulate(reconstructed, 2, False) == [0, 0, 0, 0]


@squin.kernel
def allocated_length(n: int):
    qs = squin.qalloc(n)
    return len(qs)


@pytest.mark.parametrize("size", [0, 1, 3])
def test_runtime_length_uses_the_allocated_register(size):
    wired = SquinToWire().emit(allocated_length)
    reconstructed = WireToSquin().emit(wired)
    assert simulate(reconstructed, size) == simulate(allocated_length, size) == size


def test_runtime_allocation_passes_its_size_without_a_guard():
    wired = SquinToWire().emit(allocated_length)
    allocation = next(
        node for node in wired.code.walk() if isinstance(node, stmts.AllocRegister)
    )
    assert allocation.size is wired.callable_region.blocks[0].args[1]
    assert not any(
        isinstance(node, (py.cmp.Lt, scf.IfElse)) for node in wired.code.walk()
    )


@squin.kernel
def negative_allocation(n: int):
    qs = squin.qalloc(n - n - 1)
    return len(qs)


def test_allocation_rejects_a_provably_negative_size():
    with pytest.raises(
        WireConversionError, match="allocation size must be nonnegative"
    ):
        SquinToWire().emit(negative_allocation)


@squin.kernel
def returns_tuple_from_branch(flag: bool):
    values = (1, 2)
    if flag:
        values = (3, 4)
    return values


@pytest.mark.parametrize("flag, expected", [(False, [1, 2]), (True, [3, 4])])
def test_return_unpacks_classical_tuple_results_from_regions(flag, expected):
    wired = SquinToWire().emit(returns_tuple_from_branch)
    assert simulate(WireToSquin().emit(wired), flag) == expected


@squin.kernel
def returns_typed_tuple_from_branch(flag: bool, n: int) -> tuple[int, int]:
    values = (n, n + 1)
    if flag:
        values = (n + 2, n + 3)
    return values


@pytest.mark.parametrize("flag, expected", [(False, [5, 6]), (True, [7, 8])])
def test_return_unpacks_known_tuple_fields_from_regions(flag, expected):
    wired = SquinToWire().emit(returns_typed_tuple_from_branch)
    assert simulate(WireToSquin().emit(wired), flag, 5) == expected


@squin.kernel
def measured(q: Qubit):
    return squin.measure(q)


@squin.kernel
def calls_measured():
    q = squin.qubit.new()
    return measured(q)


def test_a_call_result_has_the_inferred_type_of_its_callee():
    converter = SquinToWire()
    converter.emit(calls_measured)
    callee = converter.converted[measured]
    emitted = EmitWire(
        calls_measured.dialects, calls_measured, converter.converted
    ).emit_method()
    call = next(
        node for node in emitted.callable_region.walk() if isinstance(node, func.Invoke)
    )
    fields = [use.stmt.results[0].type for use in call.result.uses]
    assert all(isinstance(use.stmt, py.GetItem) for use in call.result.uses)
    assert call.result.type == callee.return_type
    assert sorted(map(str, fields)) == sorted(map(str, callee.return_type.vars))


@squin.kernel
def paired_slices():
    qs = squin.qalloc(4)
    squin.broadcast.cx(qs[0:2], qs[2:4])


def test_library_operations_take_the_location_of_the_user_call():
    call = next(
        node
        for node in paired_slices.code.walk()
        if isinstance(node, func.Invoke) and node.callee.sym_name == "cx"
    )
    wired = SquinToWire().emit(paired_slices)
    emitted = (stmts.TakeSlice, stmts.PutSlice, stmts.RegisterGate)
    sources = [node.source for node in wired.code.walk() if isinstance(node, emitted)]
    assert call.source is not None and len(sources) == 5
    assert {None if s is None else s.lineno for s in sources} == {call.source.lineno}


@squin.kernel
def summed(n: int) -> int:
    total = 0
    for i in range(n):
        total = total + i
    return total


def test_a_return_inside_a_loop_body_is_rejected():
    method = summed.similar()
    loop = next(n for n in method.callable_region.walk() if isinstance(n, scf.For))
    end = loop.body.blocks[0].last_stmt
    assert isinstance(end, scf.Yield)
    end.replace_by(func.Return(end.values[0]))
    with pytest.raises(WireConversionError, match="function-level return"):
        EmitWire(method.dialects, method, {}).emit_method()


@squin.kernel
def flip_last(qs: ilist.IList[Qubit, Any]):
    squin.x(qs[len(qs) - 1])


@squin.kernel
def repeated_wrapper(n: int):
    first = squin.qalloc(3)
    flip_last(first)
    second = squin.qalloc(n)
    flip_last(second)
    third = squin.qalloc(4)
    flip_last(third)
    return squin.broadcast.measure(second), squin.broadcast.measure(third)


@pytest.mark.parametrize("size", [2, 3, 5])
def test_library_calls_use_the_length_of_their_own_argument(monkeypatch, size):
    monkeypatch.setattr(
        flip_last, "mod", ModuleType("bloqade.squin.stdlib.test_lengths")
    )
    restored = WireToSquin().emit(SquinToWire().emit(repeated_wrapper))
    expected = [[0] * (size - 1) + [1], [0, 0, 0, 1]]
    assert simulate(restored, size) == simulate(repeated_wrapper, size) == expected


@squin.kernel
def mixed_loop(n: int):
    value = 0
    for _ in range(n):
        value = value + 0.5
    return value


@squin.kernel
def call_mixed_loop(n: int):
    return mixed_loop(n)


@pytest.mark.parametrize("source", [mixed_loop, call_mixed_loop])
@pytest.mark.parametrize("count", [0, 2])
def test_return_types_include_the_zero_iteration_loop_result(source, count):
    wired = SquinToWire().emit(source)
    assert types.Int.is_subseteq(wired.return_type)
    assert types.Float.is_subseteq(wired.return_type)
    restored = WireToSquin().emit(wired)
    assert simulate(restored, count) == simulate(source, count) == count * 0.5
    if count == 0:
        assert type(simulate(restored, count)) is int
