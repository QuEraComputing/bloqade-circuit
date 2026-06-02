import math

import pytest
from kirin.ir.exception import ValidationErrorGroup
from kirin.validation import ValidationSuite

from bloqade import squin
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.squin.analysis.validation import CliffordValidation


def test_clifford_kernel_validates():
    @squin.kernel
    def main_clifford():
        q = squin.qalloc(4)
        squin.h(q[0])
        squin.s(q[1])
        squin.sqrt_x(q[2])
        squin.cx(q[0], q[1])
        squin.cy(q[1], q[2])
        squin.cz(q[2], q[3])

    AggressiveUnroll(main_clifford.dialects).fixpoint(main_clifford)

    _, errors = CliffordValidation().run(main_clifford)
    assert len(errors) == 0


def test_non_clifford_t_gate_is_rejected():
    @squin.kernel
    def main_nonclifford():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.t(q[1])

    AggressiveUnroll(main_nonclifford.dialects).fixpoint(main_nonclifford)

    validation_suite = ValidationSuite([CliffordValidation])
    result = validation_suite.validate(main_nonclifford)
    assert result.error_count() == 1

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_non_clifford_rotation_is_rejected():
    @squin.kernel
    def main_nonclifford():
        q = squin.qalloc(1)
        squin.rx(0.3 * math.pi, q[0])

    AggressiveUnroll(main_nonclifford.dialects).fixpoint(main_nonclifford)

    _, errors = CliffordValidation().run(main_nonclifford)
    assert len(errors) == 1
    assert "Rx" in str(errors[0])


def test_clifford_rotations_are_allowed():
    @squin.kernel
    def main_clifford():
        q = squin.qalloc(3)
        squin.rx(math.pi / 2, q[0])
        squin.ry(math.pi, q[1])
        squin.rz(3 * math.pi / 2, q[2])

    AggressiveUnroll(main_clifford.dialects).fixpoint(main_clifford)

    _, errors = CliffordValidation().run(main_clifford)
    assert len(errors) == 0


def test_clifford_u3_is_allowed_and_non_clifford_u3_is_rejected():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.u3(0.25 * math.tau, 0.0, 0.5 * math.tau, q[0])
        squin.u3(0.3 * math.pi, 0.24 * math.pi, 0.49 * math.pi, q[1])

    AggressiveUnroll(main.dialects).fixpoint(main)

    _, errors = CliffordValidation().run(main)
    assert len(errors) == 1
    assert "U3" in str(errors[0])
