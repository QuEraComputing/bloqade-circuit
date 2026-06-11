import math

import pytest
from kirin.dialects import py
from kirin.validation import ValidationSuite
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.squin.analysis.validation import CliffordValidation
from bloqade.squin.analysis.validation.clifford import _constant_turn


def _stmt_type_names(method):
    return [type(stmt).__name__ for stmt in method.callable_region.walk()]


def test_clifford_validation_name():
    assert CliffordValidation().name() == "Clifford Validation"


def test_clifford_validation_does_not_mutate_kernel():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.h(q[0])

    before = _stmt_type_names(main)

    _, errors = CliffordValidation().run(main)

    assert len(errors) == 0
    assert _stmt_type_names(main) == before


def test_clifford_kernel_allowed():
    @squin.kernel
    def main():
        q = squin.qalloc(4)
        squin.h(q[0])
        squin.s(q[0])
        squin.sqrt_x(q[1])
        squin.sqrt_y_adj(q[1])
        squin.cx(q[0], q[1])
        squin.cy(q[1], q[2])
        squin.cz(q[2], q[3])

    _, errors = CliffordValidation().run(main)
    assert len(errors) == 0


def test_non_clifford_t_gate_rejected():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.t(q[0])
        squin.cx(q[0], q[1])

    suite = ValidationSuite([CliffordValidation])
    result = suite.validate(main)
    assert result.error_count() == 1

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_quarter_turn_rotation_allowed():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        squin.rx(math.pi / 2, q[0])
        squin.ry(math.pi, q[1])
        squin.rz(3 * math.pi / 2, q[2])

    _, errors = CliffordValidation().run(main)
    assert len(errors) == 0


def test_non_clifford_rotation_rejected():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.rz(math.pi / 4, q[0])

    suite = ValidationSuite([CliffordValidation])
    result = suite.validate(main)
    assert result.error_count() == 1

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_symbolic_rotation_rejected():
    @squin.kernel
    def main(angle: float):
        q = squin.qalloc(1)
        squin.rx(angle, q[0])

    suite = ValidationSuite([CliffordValidation])
    result = suite.validate(main)
    assert result.error_count() == 1

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_u3_clifford_gate_allowed():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.u3(0.0, 0.0, math.pi / 2, q[0])

    _, errors = CliffordValidation().run(main)
    assert len(errors) == 0


def test_phased_xz_quarter_turns_allowed():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.phased_xz(math.pi / 2, math.pi, 0.0, q[0])

    _, errors = CliffordValidation().run(main)
    assert len(errors) == 0


def test_phased_xz_non_quarter_turn_rejected():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.phased_xz(math.pi / 4, 0.0, 0.0, q[0])

    suite = ValidationSuite([CliffordValidation])
    result = suite.validate(main)
    assert result.error_count() == 1

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_non_numeric_constant_turn_rejected():
    value = py.Constant(value="not numeric").result

    assert _constant_turn(value) is None
