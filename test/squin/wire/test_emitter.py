"""Check direct wire emission through Kirin's region interpreter."""

from collections import Counter

import pytest
from kirin.dialects import py, scf, func
from test_roundtrip import nested, simulate

from bloqade import squin
from bloqade.types import Qubit
from bloqade.squin.wire import WireConversionError, stmts
from bloqade.squin.emit.wire import EmitWire
from bloqade.squin.passes.wire_target import ConversionTarget
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin
from bloqade.squin.analysis.validation.wire import WireValidation


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


@pytest.mark.parametrize("size", [-2, 0, 3])
def test_runtime_length_uses_the_allocated_register(size):
    wired = SquinToWire().emit(allocated_length)
    reconstructed = WireToSquin().emit(wired)
    assert (
        simulate(reconstructed, size)
        == simulate(allocated_length, size)
        == max(0, size)
    )


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
