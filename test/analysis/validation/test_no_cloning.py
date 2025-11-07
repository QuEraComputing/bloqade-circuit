from typing import Any, List, TypeVar

import pytest
from kirin import ir
from kirin.analysis import ForwardFrame
from kirin.dialects.ilist.runtime import IList

from bloqade import squin
from bloqade.types import Qubit
from bloqade.analysis.validation.nocloning.lattice import May, Must, QubitValidation
from bloqade.analysis.validation.nocloning.analysis import NoCloningValidation

T = TypeVar("T", bound=Must | May)


def collect_errors(frame: ForwardFrame[QubitValidation], typ: type[T]) -> List[str]:
    """Collect individual violation strings from all QubitValidation entries of type `typ`."""
    violations: List[str] = []
    for validation_val in frame.entries.values():
        if isinstance(validation_val, typ):
            for v in validation_val.violations:
                violations.append(v)
    return violations


@pytest.mark.parametrize("control_gate", [squin.cx, squin.cy, squin.cz])
def test_fail(control_gate: ir.Method[[Qubit, Qubit], Any]):
    @squin.kernel
    def bad_control():
        q = squin.qalloc(1)
        control_gate(q[0], q[0])

    validation = NoCloningValidation(bad_control)
    validation.initialize()
    frame, _ = validation.run_analysis(bad_control)
    print()
    bad_control.print(analysis=frame.entries)
    must_errors = collect_errors(frame, Must)
    may_errors = collect_errors(frame, May)
    assert len(must_errors) == 1
    assert len(may_errors) == 0
    with pytest.raises(Exception):
        validation.raise_validation_errors()


@pytest.mark.parametrize("control_gate", [squin.cx, squin.cy, squin.cz])
def test_conditionals_fail(control_gate: ir.Method[[Qubit, Qubit], Any]):
    @squin.kernel
    def bad_control(cond: bool):
        q = squin.qalloc(10)
        if cond:
            control_gate(q[0], q[0])
        else:
            control_gate(q[0], q[1])
        squin.cx(q[1], q[1])

    validation = NoCloningValidation(bad_control)
    validation.initialize()
    frame, _ = validation.run_analysis(bad_control)
    print()
    bad_control.print(analysis=frame.entries)
    must_errors = collect_errors(frame, Must)
    may_errors = collect_errors(frame, May)
    assert len(must_errors) == 2
    assert len(may_errors) == 0
    with pytest.raises(Exception):
        validation.raise_validation_errors()


@pytest.mark.parametrize("control_gate", [squin.cx, squin.cy, squin.cz])
def test_pass(control_gate: ir.Method[[Qubit, Qubit], Any]):
    @squin.kernel
    def test():
        q = squin.qalloc(3)
        control_gate(q[0], q[1])
        squin.rx(1.57, q[0])
        squin.measure(q[0])
        control_gate(q[0], q[2])

    validation = NoCloningValidation(test)
    validation.initialize()
    frame, _ = validation.run_analysis(test)
    print()
    test.print(analysis=frame.entries)
    must_errors = collect_errors(frame, Must)
    may_errors = collect_errors(frame, May)
    assert len(must_errors) == 0
    assert len(may_errors) == 0


def test_fail_2():
    @squin.kernel
    def good_kernel():
        q = squin.qalloc(2)
        a = 1
        squin.cx(q[0], q[1])
        squin.cy(q[1], q[a])

    validation = NoCloningValidation(good_kernel)
    validation.initialize()
    frame, _ = validation.run_analysis(good_kernel)
    must_errors = collect_errors(frame, Must)
    may_errors = collect_errors(frame, May)
    assert len(must_errors) == 1
    assert len(may_errors) == 0
    with pytest.raises(Exception):
        validation.raise_validation_errors()


def test_parallel_fail():
    @squin.kernel
    def bad_kernel():
        q = squin.qalloc(5)
        squin.broadcast.cx(IList([q[0], q[1], q[2]]), IList([q[1], q[2], q[3]]))

    validation = NoCloningValidation(bad_kernel)
    validation.initialize()
    frame, _ = validation.run_analysis(bad_kernel)
    print()
    bad_kernel.print(analysis=frame.entries)
    must_errors = collect_errors(frame, Must)
    may_errors = collect_errors(frame, May)
    assert len(must_errors) == 2
    assert len(may_errors) == 0
    with pytest.raises(Exception):
        validation.raise_validation_errors()


def test_potential_fail():
    @squin.kernel
    def bad_kernel(a: int, b: int):
        q = squin.qalloc(5)
        squin.cx(q[a], q[2])

    validation = NoCloningValidation(bad_kernel)
    validation.initialize()
    frame, _ = validation.run_analysis(bad_kernel)
    print()
    bad_kernel.print(analysis=frame.entries)
    must_errors = collect_errors(frame, Must)
    may_errors = collect_errors(frame, May)
    assert len(must_errors) == 0
    assert len(may_errors) == 1
    with pytest.raises(Exception):
        validation.raise_validation_errors()


def test_potential_parallel_fail():
    @squin.kernel
    def bad_kernel(a: IList):
        q = squin.qalloc(5)
        squin.broadcast.cx(a, IList([q[2], q[3], q[4]]))

    validation = NoCloningValidation(bad_kernel)
    validation.initialize()
    frame, _ = validation.run_analysis(bad_kernel)
    print()
    bad_kernel.print(analysis=frame.entries)
    must_errors = collect_errors(frame, Must)
    may_errors = collect_errors(frame, May)
    assert len(must_errors) == 0
    assert len(may_errors) == 1
    with pytest.raises(Exception):
        validation.raise_validation_errors()
