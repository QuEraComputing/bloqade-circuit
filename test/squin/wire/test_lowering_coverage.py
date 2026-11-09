"""Compare direct Python lowering with established Squin circuit behavior."""

import linecache
from types import FunctionType
from typing import Any, Literal

import numpy as np
import pytest
from kirin import lowering
from test_forms import (
    diamond,
    lengths,
    tuple_slice,
    slice_in_loop,
    negative_index,
    empty_broadcast,
    slice_in_branch,
    measured_single_tuple,
    calls_classical_helper,
)
from kirin.dialects import func, ilist
from test_broadcast import (
    paired,
    paired_noise,
    unknown_length,
    three_registers,
    adjoints_and_reset,
)
from test_roundtrip import CASES, plain, simulate
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.types import Qubit
from bloqade.pyqrack import DynamicMemorySimulator
from bloqade.squin.wire import Operation, AllocRegister
from bloqade.squin.emit.wire import EmitWire
from bloqade.squin.wire.lowering import wire_kernel
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin
from bloqade.squin.rewrite.wire.sources import ENTRIES, Entry, entry_of


@pytest.mark.parametrize(
    "source,args,expected",
    [
        *CASES,
        (diamond, (), 0),
        (empty_broadcast, (), [0, 1]),
        (negative_index, (), [0, 0, 1]),
        (tuple_slice, (), [0, 1, 0]),
        (lengths, (), 5),
        (calls_classical_helper, (), 1),
        (measured_single_tuple, (), [1]),
        (slice_in_branch, (False,), [0, 0, 0, 0]),
        (slice_in_branch, (True,), [0, 1, 1, 0]),
        (slice_in_loop, (0,), [0, 0, 0, 0]),
        (slice_in_loop, (3,), [0, 1, 1, 0]),
        *(
            (source, (n,), [bit] * n)
            for source, bit in (
                (unknown_length, 1),
                (paired, 1),
                (three_registers, 1),
                (adjoints_and_reset, 0),
            )
            for n in (0, 1, 4)
        ),
        (paired_noise, (3, 2), [1, 1]),
    ],
)
def test_existing_circuits_compile_directly(source, args, expected, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Direct lowering must emit each Python expression itself.")

    monkeypatch.setattr(SquinToWire, "emit", forbidden)
    monkeypatch.setattr(EmitWire, "emit_method", forbidden)
    before = source.code.print_str()
    wired = wire_kernel(source.py_func)
    assert simulate(WireToSquin().emit(wired), *args) == expected
    assert source.code.print_str() == before


def source_function(source: str, namespace: dict[str, Any]) -> FunctionType:
    """Create a test function whose source Kirin can read through inspect."""
    name = f"<wire-lowering-{len(linecache.cache)}>"
    linecache.cache[name] = (len(source), None, source.splitlines(keepends=True), name)
    exec(compile(source, name, "exec"), namespace)
    return namespace["program"]


@pytest.mark.parametrize(
    "entry", list(ENTRIES.values()), ids=lambda entry: entry.source.__name__
)
@pytest.mark.parametrize("scalar", [False, True])
def test_every_mapped_operation_has_direct_lowering(entry: Entry, scalar: bool):
    qubits = {name: f"q{i}" for i, name in enumerate(entry.qubits)}
    allocations = "".join(f"    {name} = squin.qalloc(2)\n" for name in qubits.values())
    arguments = {
        name: f"[{qubits[name]}[0]]" if scalar else qubits[name]
        for name in entry.qubits
    }
    arguments.update(
        {
            name: repr([0.0] * 15) if name == "probabilities" else "0.125"
            for name in entry.params
        }
    )
    if entry.has_adjoint:
        arguments["adjoint"] = "True"
    call = ", ".join(f"{name}={value}" for name, value in arguments.items())
    function = source_function(
        f"def program() -> None:\n{allocations}    operation({call})\n",
        {"squin": squin, "operation": entry.source},
    )
    wired = wire_kernel(function)
    operations = [node for node in wired.code.walk() if isinstance(node, Operation)]
    assert len(operations) == 1
    assert entry_of(operations[0]) is entry
    WireToSquin().emit(wired)


@wire_kernel
def flip_if(q: Qubit, flag: bool) -> int:
    if flag:
        squin.x(q)
    return 7


@pytest.mark.parametrize("flag", [False, True])
def test_direct_helpers_thread_quantum_parameters_and_classical_results(flag):
    @wire_kernel
    def program(flag: bool):
        qs = squin.qalloc(1)
        answer = flip_if(qs[0], flag=flag)
        return squin.broadcast.measure(qs), answer

    assert simulate(WireToSquin().emit(program), flag) == [[int(flag)], 7]
    assert any(isinstance(stmt, func.Invoke) for stmt in program.code.walk())


@pytest.mark.parametrize("n", [0, 1, 4])
def test_register_iteration_carries_the_register(n):
    @wire_kernel
    def program(n: int):
        qs = squin.qalloc(n)
        for q in qs:
            squin.x(q)
        return squin.broadcast.measure(qs)

    assert simulate(WireToSquin().emit(program), n) == [1] * n


@pytest.mark.parametrize("n", [0, 3])
@pytest.mark.parametrize("flag", [False, True])
def test_classical_assignments_and_conditional_expressions(n, flag):
    @wire_kernel
    def program(n: int, flag: bool):
        value = 2
        for i in range(n):
            value += 0.5
        selected = value if flag else 3
        return value, selected, (n and 7), (n or 9)

    value = 2 + n * 0.5 if n else 2
    expected = [value, value if flag else 3, n and 7, n or 9]
    assert simulate(WireToSquin().emit(program), n, flag) == expected


@pytest.mark.parametrize("value", [0, 1])
def test_boolean_operators_evaluate_only_the_selected_operand(value):
    @wire_kernel
    def program(value: int):
        return value and (7 // value)

    assert simulate(WireToSquin().emit(program), value) == (0 if value == 0 else 7)


@pytest.mark.parametrize("returned", ["qs", "qs[0]", "(1, qs)", "[qs[0]]"])
def test_quantum_returns_fail_with_a_source_error(returned):
    function = source_function(
        f"def program():\n    qs = squin.qalloc(2)\n    return {returned}\n",
        {"squin": squin},
    )
    with pytest.raises(lowering.BuildError, match="cannot return quantum values"):
        wire_kernel(function)


@wire_kernel
def flip_pair(qs: ilist.IList[Qubit, Any]) -> None:
    squin.broadcast.x(qs)


@wire_kernel
def tuple_sum(values: tuple[int, int]) -> int:
    return values[0] + values[1]


def test_helpers_accept_quantum_lists_and_classical_tuples():
    @wire_kernel
    def program():
        qs = squin.qalloc(3)
        flip_pair([qs[0], qs[2]])
        answer = tuple_sum((2, 3))
        return squin.broadcast.measure(qs), answer

    assert simulate(WireToSquin().emit(program)) == [[1, 0, 1], 5]


@pytest.mark.parametrize("probability", [0.0, 1.0])
@pytest.mark.parametrize("dynamic", [False, True])
def test_correlated_loss_preserves_the_shared_group_event(probability, dynamic):
    @wire_kernel
    def program(n: int, probability: float):
        qs = squin.qalloc(n)
        squin.correlated_qubit_loss(probability, qs)
        return squin.broadcast.measure(qs)

    @wire_kernel
    def grouped(probability: float):
        qs = squin.qalloc(4)
        squin.broadcast.correlated_qubit_loss(
            probability, [[qs[0], qs[2]], [qs[1], qs[3]]]
        )
        return squin.broadcast.measure(qs)

    wired = program if dynamic else grouped
    args = (4, probability) if dynamic else (probability,)
    restored = WireToSquin().emit(wired)
    assert simulate(restored, *args) == [int(probability)] * 4


@pytest.mark.parametrize("n", [0, 3])
def test_correlated_loss_accepts_runtime_rows(n):
    @wire_kernel
    def lose_rows(rows: ilist.IList[ilist.IList[Qubit, Literal[2]], Any]) -> None:
        squin.broadcast.correlated_qubit_loss(1.0, rows)

    restored = WireToSquin().emit(lose_rows)

    @squin.kernel
    def program(n: int):
        qs = squin.qalloc(2 * n)
        restored(qs)
        return squin.broadcast.measure(qs)

    assert simulate(program, n) == [1] * (2 * n)


@pytest.mark.parametrize("duplicate", [False, True])
def test_packed_helper_arguments_require_distinct_qubits(duplicate):
    returned = "i" if duplicate else "j"
    function = source_function(
        f"def program(i: int, j: int):\n    qs = squin.qalloc(3)\n    flip_pair([qs[i], qs[{returned}]])\n",
        {"squin": squin, "flip_pair": flip_pair},
    )
    with pytest.raises(ValidationErrorGroup, match="already out|Cannot prove"):
        wire_kernel(function)


@pytest.mark.parametrize(
    "predicate",
    [squin.broadcast.is_one, squin.broadcast.is_zero, squin.broadcast.is_lost],
)
def test_runtime_measurement_predicates_compile(predicate):
    @wire_kernel
    def program(n: int):
        qs = squin.qalloc(n)
        return predicate(squin.broadcast.measure(qs))

    WireToSquin().emit(program)


def test_quantum_annotations_require_the_declared_type():
    with pytest.raises(lowering.BuildError, match="does not match its annotation"):

        @wire_kernel
        def program():
            qs = squin.qalloc(2)
            q: float = qs[0]
            squin.x(q)


def test_correlated_groups_share_one_random_loss_event():
    @wire_kernel
    def program():
        qs = squin.qalloc(4)
        squin.broadcast.correlated_qubit_loss(0.5, [[qs[0], qs[2]], [qs[1], qs[3]]])
        return squin.broadcast.measure(qs)

    restored = WireToSquin().emit(program)
    expected_rng = np.random.default_rng(17)
    simulator = DynamicMemorySimulator(rng_state=np.random.default_rng(17))
    for _ in range(8):
        first, second = (int(value <= 0.5) for value in expected_rng.uniform(size=2))
        assert plain(simulator.run(restored)) == [first, second, first, second]


@wire_kernel
def choose_pair(q: Qubit, n: int, flag: bool):
    pair = (n, n + 1) if flag else (n + 2, n + 3)
    squin.x(q)
    return pair


@wire_kernel
def empty_tuple(q: Qubit):
    squin.x(q)
    return ()


@pytest.mark.parametrize("flag", [False, True])
def test_helper_results_preserve_classical_tuple_shapes(flag):
    @wire_kernel
    def program(n: int, flag: bool):
        qs = squin.qalloc(2)
        pair = choose_pair(qs[0], n, flag)
        empty = empty_tuple(qs[1])
        return pair, empty, squin.broadcast.measure(qs)

    assert simulate(WireToSquin().emit(program), 3, flag) == [
        [3, 4] if flag else [5, 6],
        [],
        [1, 1],
    ]


def test_return_annotations_require_the_declared_type():
    with pytest.raises(lowering.BuildError, match="does not match its annotation"):

        @wire_kernel
        def program() -> int:
            return 1.5


def test_runtime_allocation_uses_the_requested_size():
    @wire_kernel
    def program(n: int) -> None:
        qs = squin.qalloc(n)
        squin.broadcast.x(qs)

    (allocation,) = (
        node for node in program.code.walk() if isinstance(node, AllocRegister)
    )
    assert allocation.size is program.callable_region.blocks[0].args[1]
