from typing import Any, TypeVar

import pytest
from kirin import ir
from kirin.dialects.ilist.runtime import IList

from bloqade import squin
from bloqade.types import Qubit
from bloqade.analysis.validation.nocloning.lattice import May, Must
from bloqade.analysis.validation.nocloning.analysis import NoCloningValidation

T = TypeVar("T", bound=Must | May)


def collect_errors_from_validation(
    validation: NoCloningValidation,
    frame,
) -> tuple[int, int]:
    """Count Must (definite) and May (potential) errors from the validation pass.

    Returns:
        (must_count, may_count) - number of definite and potential violations
    """
    must_count = 0
    may_count = 0

    if validation._analysis is None:
        return (must_count, may_count)

    for node, value in frame.entries.items():
        if isinstance(value, Must):
            must_count += len(value.violations)
        elif isinstance(value, May):
            may_count += len(value.violations)

    return must_count, may_count


@pytest.mark.parametrize("control_gate", [squin.cx, squin.cy, squin.cz])
def test_fail(control_gate: ir.Method[[Qubit, Qubit], Any]):
    @squin.kernel
    def bad_control():
        q = squin.qalloc(1)
        control_gate(q[0], q[0])

    validation = NoCloningValidation()

    frame, errors = validation.run(bad_control)
    print()
    bad_control.print(analysis=frame.entries)

    must_count, may_count = collect_errors_from_validation(validation, frame)
    assert must_count == 1
    assert may_count == 0


@pytest.mark.parametrize("control_gate", [squin.cx])
def test_conditionals_fail(control_gate: ir.Method[[Qubit, Qubit], Any]):
    @squin.kernel
    def bad_control(cond: bool):
        q = squin.qalloc(10)
        if cond:
            control_gate(q[0], q[0])
        else:
            control_gate(q[0], q[1])
        squin.cx(q[1], q[1])

    validation = NoCloningValidation()
    frame, errors = validation.run(bad_control)
    print()
    bad_control.print(analysis=frame.entries)

    must_count, may_count = collect_errors_from_validation(validation, frame)
    assert must_count == 1  # squin.cx(q[1], q[1]) outside conditional
    assert may_count == 1  # control_gate(q[0], q[0]) inside conditional


@pytest.mark.parametrize("control_gate", [squin.cx, squin.cy, squin.cz])
def test_pass(control_gate: ir.Method[[Qubit, Qubit], Any]):
    @squin.kernel
    def test():
        q = squin.qalloc(3)
        control_gate(q[0], q[1])
        squin.rx(1.57, q[0])
        squin.measure(q[0])
        control_gate(q[0], q[2])

    validation = NoCloningValidation()
    frame, errors = validation.run(test)
    print()
    test.print(analysis=frame.entries)

    must_count, may_count = collect_errors_from_validation(validation, frame)
    assert must_count == 0
    assert may_count == 0


def test_fail_2():
    @squin.kernel
    def good_kernel():
        q = squin.qalloc(2)
        a = 1
        squin.cx(q[0], q[1])
        squin.cy(q[1], q[a])

    validation = NoCloningValidation()
    frame, errors = validation.run(good_kernel)

    must_count, may_count = collect_errors_from_validation(validation, frame)
    assert must_count == 1
    assert may_count == 0


def test_parallel_fail():
    @squin.kernel
    def bad_kernel():
        q = squin.qalloc(5)
        squin.broadcast.cx(IList([q[0], q[1], q[2]]), IList([q[1], q[2], q[3]]))

    validation = NoCloningValidation()
    frame, errors = validation.run(bad_kernel)
    print()
    bad_kernel.print(analysis=frame.entries)

    must_count, may_count = collect_errors_from_validation(validation, frame)
    assert must_count == 2
    assert may_count == 0


def test_potential_fail():
    @squin.kernel
    def bad_kernel(a: int, b: int):
        q = squin.qalloc(5)
        squin.cx(q[a], q[2])

    validation = NoCloningValidation()
    frame, errors = validation.run(bad_kernel)
    print()
    bad_kernel.print(analysis=frame.entries)

    must_count, may_count = collect_errors_from_validation(validation, frame)
    assert must_count == 0
    assert may_count == 1


def test_potential_parallel_fail():
    @squin.kernel
    def bad_kernel(a: IList):
        q = squin.qalloc(5)
        squin.broadcast.cx(a, IList([q[2], q[3], q[4]]))

    validation = NoCloningValidation()
    frame, errors = validation.run(bad_kernel)
    print()
    bad_kernel.print(analysis=frame.entries)

    must_count, may_count = collect_errors_from_validation(validation, frame)
    assert must_count == 0
    assert may_count == 1
