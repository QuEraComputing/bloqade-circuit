from typing import Any

import pytest
from util import collect_validation_errors
from kirin import ir
from kirin.dialects.ilist.runtime import IList

from bloqade import squin
from bloqade.types import Qubit
from bloqade.analysis.validation.nocloning.lattice import QubitValidation
from bloqade.analysis.validation.nocloning.analysis import NoCloningValidation


@pytest.mark.parametrize("control_gate", [squin.cx, squin.cy, squin.cz])
def test_control_gate_fail(control_gate: ir.Method[[Qubit, Qubit], Any]):
    @squin.kernel
    def bad_control():
        q = squin.qalloc(1)
        control_gate(q[0], q[0])

    validation = NoCloningValidation(bad_control)
    validation.initialize()
    frame, _ = validation.run_analysis(bad_control)
    print()
    bad_control.print(analysis=frame.entries)
    validation_errors = collect_validation_errors(frame, QubitValidation)
    assert len(validation_errors) == 1


@pytest.mark.parametrize("control_gate", [squin.cx, squin.cy, squin.cz])
def test_control_gate_conditionals_fail(control_gate: ir.Method[[Qubit, Qubit], Any]):
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
    validation_errors = collect_validation_errors(frame, QubitValidation)
    # print("Violations:", validation_errors)
    assert len(validation_errors) == 2


@pytest.mark.parametrize("control_gate", [squin.cx, squin.cy, squin.cz])
def test_control_gate_parallel_fail(control_gate: ir.Method[[Qubit, Qubit], Any]):
    @squin.kernel
    def bad_control():
        q = squin.qalloc(2)
        control_gate(q[0], q[1])

    validation = NoCloningValidation(bad_control)
    validation.initialize()
    frame, _ = validation.run_analysis(bad_control)
    print()
    bad_control.print(analysis=frame.entries)
    validation_errors = collect_validation_errors(frame, QubitValidation)
    assert len(validation_errors) == 0


def test_control_gate_parallel_pass():
    @squin.kernel
    def good_kernel():
        q = squin.qalloc(2)
        squin.cx(q[0], q[1])
        squin.cy(q[1], q[1])

    validation = NoCloningValidation(good_kernel)
    validation.initialize()
    frame, _ = validation.run_analysis(good_kernel)
    print()
    good_kernel.print(analysis=frame.entries)
    validation_errors = collect_validation_errors(frame, QubitValidation)
    assert len(validation_errors) == 1
