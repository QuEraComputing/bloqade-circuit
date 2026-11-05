"""Check conversion boundaries, failure isolation and bounded rewrite execution."""

from typing import Any, Literal

import pytest
from kirin import ir
from kirin.dialects import py, ilist
from test_roundtrip import calls, simulate
from test_completion import identical_operands
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.types import Qubit
from bloqade.squin.wire import WireConversionError
from bloqade.squin.rewrite.wire.tools import CheckedFixpoint
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin


class AlwaysChanges(RewriteRule):
    """Report a rewrite on every visit to exercise the convergence limit."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Keep the driver running without changing the test statement."""
        return RewriteResult(has_done_something=True)


def test_rewrite_exhaustion_is_an_error():
    with pytest.raises(WireConversionError, match="within 2 iterations"):
        CheckedFixpoint(AlwaysChanges(), max_iter=2).rewrite(py.Constant(0))


def test_one_converter_recovers_after_failure_and_produces_deterministic_output():
    converter = SquinToWire()
    before = identical_operands.code.print_str()
    with pytest.raises(ValidationErrorGroup, match="already out of its register"):
        converter.emit(identical_operands)
    assert identical_operands.code.print_str() == before
    first = converter.emit(calls)
    second = converter.emit(calls)
    assert first.code.print_str() == second.code.print_str()
    assert simulate(WireToSquin().emit(second)) == [[1, 0, 1, 1, 1], 4]


@squin.kernel
def recursive(q: Qubit, n: int):
    squin.x(q)
    if n > 0:
        recursive(q, n - 1)


def test_recursive_calls_fail_before_conversion():
    before = recursive.code.print_str()
    with pytest.raises(WireConversionError, match="recursive calls"):
        SquinToWire().emit(recursive)
    assert recursive.code.print_str() == before


@squin.kernel
def repeated_return():
    q = squin.qubit.new()
    return q, q


@squin.kernel
def repeated_register_return():
    qs = squin.qalloc(2)
    return qs, qs


@squin.kernel
def returned_fresh():
    return squin.qubit.new()


@squin.kernel
def returned_parameter(q: Qubit) -> Qubit:
    return q


@pytest.mark.parametrize(
    "kernel",
    [returned_fresh, returned_parameter, repeated_return, repeated_register_return],
)
def test_a_function_cannot_return_qubits(kernel):
    before = kernel.code.print_str()
    with pytest.raises(WireConversionError, match="cannot return qubits"):
        SquinToWire().emit(kernel)
    assert kernel.code.print_str() == before


@squin.kernel
def flip(q: Qubit):
    squin.x(q)


def twice(callee):
    @squin.kernel
    def caller(q: Qubit):
        callee(q)
        callee(q)

    return caller


def test_validation_interprets_each_callee_once(monkeypatch):
    from collections import Counter

    from kirin.interp.abc import InterpreterABC

    from bloqade.squin.analysis.validation.wire import WireValidation

    top = flip
    for _ in range(4):
        top = twice(top)
    wired = SquinToWire().emit(top)
    visits = Counter()
    frame_call = InterpreterABC.frame_call

    def record(interpreter, frame, node, *args, **kwargs):
        visits[type(interpreter).__name__, node] += 1
        return frame_call(interpreter, frame, node, *args, **kwargs)

    monkeypatch.setattr(InterpreterABC, "frame_call", record)
    WireValidation().check(wired)
    assert len(visits) == 3 * 5
    assert set(visits.values()) == {1}


@squin.kernel
def three(qs: ilist.IList[Qubit, Literal[3]]):
    squin.broadcast.x(qs)


@squin.kernel
def runtime_register(n: int):
    qs = squin.qalloc(n)
    three(qs)
    return squin.broadcast.measure(qs)


@squin.kernel
def four_qubits():
    qs = squin.qalloc(4)
    three(qs)
    return squin.broadcast.measure(qs)


@squin.kernel
def three_qubits():
    qs = squin.qalloc(3)
    three(qs)
    return squin.broadcast.measure(qs)


@squin.kernel
def wide(grid: ilist.IList[ilist.IList[Qubit, Literal[2]], Literal[3]]):
    squin.x(grid[1][0])


@squin.kernel
def tall(grid: ilist.IList[ilist.IList[Qubit, Literal[3]], Literal[2]]):
    wide(grid)  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize("kernel", [runtime_register, four_qubits, tall])
def test_a_register_argument_must_have_the_declared_shape(kernel):
    with pytest.raises(WireConversionError, match="shape that its parameter"):
        SquinToWire().emit(kernel)


def test_a_register_argument_of_the_declared_length_converts():
    assert simulate(WireToSquin().emit(SquinToWire().emit(three_qubits))) == [1, 1, 1]


@squin.kernel
def flip_second(register: ilist.IList[Qubit, Any], qubit: Qubit):
    squin.x(qubit)


@squin.kernel
def register_and_its_element():
    qs = squin.qalloc(2)
    flip_second(qs, qs[0])


@squin.kernel
def flip_both(first: ilist.IList[Qubit, Any], second: ilist.IList[Qubit, Any]):
    squin.broadcast.x(first)
    squin.broadcast.z(second)


@squin.kernel
def overlapping_slices():
    qs = squin.qalloc(3)
    flip_both(qs[0:2], qs[1:3])


@squin.kernel
def flip_first(q: Qubit, qs: ilist.IList[Qubit, Any]):
    squin.x(q)


@squin.kernel
def element_and_its_register():
    qs = squin.qalloc(2)
    flip_first(qs[0], qs)


@squin.kernel
def one_qubit_twice():
    qs = squin.qalloc(1)
    return (qs[0], qs[0])


@squin.kernel
def nested_qubits():
    qs = squin.qalloc(1)
    return ((qs[0], qs[0]), 1)


@pytest.mark.parametrize(
    "kernel, reason",
    [
        (register_and_its_element, "whole register together with"),
        (element_and_its_register, "whole register together with"),
        (overlapping_slices, "already out of its register"),
        (one_qubit_twice, "cannot return qubits"),
        (nested_qubits, "cannot return qubits"),
    ],
    ids=lambda x: x if isinstance(x, str) else x.sym_name,
)
def test_a_call_or_return_that_aliases_qubits_has_no_wire_form(kernel, reason):
    with pytest.raises((WireConversionError, ValidationErrorGroup), match=reason):
        SquinToWire().emit(kernel)


def test_a_branch_rule_rejects_a_qubit_made_inside_the_branch():
    from kirin import types
    from kirin.rewrite import Walk
    from kirin.dialects import scf

    from bloqade.qubit import stmts as qubit_stmts
    from bloqade.squin.wire import WireType
    from bloqade.squin.rewrite.wire.from_wire import FromWireRegions

    flag = ir.TestValue(types.Bool)
    bodies = []
    for _ in range(2):
        block = ir.Block()
        block.args.append_from(types.Bool, "flag")
        # The statement rules have already turned the wire into a qubit.
        made = qubit_stmts.New()
        block.stmts.extend([made, scf.Yield(made.result)])
        bodies.append(ir.Region(block))
    branch = scf.IfElse(flag, *bodies)
    branch.results[0].type = WireType
    holder = ir.Block([branch])
    with pytest.raises(WireConversionError, match="exist before the branch"):
        Walk(FromWireRegions()).rewrite(holder)
