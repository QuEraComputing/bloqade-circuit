import math

import pytest
from kirin.ir.exception import ValidationErrorGroup
from kirin.validation import ValidationSuite

from bloqade import squin
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.squin.analysis.validation import CliffordValidation


def test_clifford_kernel_allowed_after_unroll():
    @squin.kernel
    def main():
        q = squin.qalloc(4)
        squin.h(q[0])
        squin.s(q[1])
        squin.sqrt_x(q[2])
        squin.cx(q[0], q[3])

    AggressiveUnroll(main.dialects).fixpoint(main)

    _, errors = CliffordValidation().run(main)

    assert errors == []


def test_non_clifford_t_gate_rejected():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.t(q[0])
        squin.cx(q[0], q[1])

    AggressiveUnroll(main.dialects).fixpoint(main)
    result = ValidationSuite([CliffordValidation]).validate(main)

    assert result.error_count() == 1
    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_non_clifford_rotation_rejected():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.rz(math.pi / 4, q[0])

    AggressiveUnroll(main.dialects).fixpoint(main)
    result = ValidationSuite([CliffordValidation]).validate(main)

    assert result.error_count() == 1
    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_quarter_turn_rotations_allowed():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        squin.rx(math.pi / 2, q[0])
        squin.ry(math.pi, q[1])
        squin.rz(3 * math.pi / 2, q[2])

    AggressiveUnroll(main.dialects).fixpoint(main)

    _, errors = CliffordValidation().run(main)

    assert errors == []


def test_clifford_u3_allowed():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.u3(0.25 * math.tau, 0.0, 0.5 * math.tau, q[0])

    AggressiveUnroll(main.dialects).fixpoint(main)

    _, errors = CliffordValidation().run(main)

    assert errors == []


def test_non_clifford_u3_rejected():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.u3(0.3 * math.pi, 0.24 * math.pi, 0.49 * math.pi, q[0])

    AggressiveUnroll(main.dialects).fixpoint(main)
    result = ValidationSuite([CliffordValidation]).validate(main)

    assert result.error_count() == 1
    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_clifford_phased_xz_allowed():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.phased_xz(math.pi / 2, math.pi, 0.0, q[0])

    AggressiveUnroll(main.dialects).fixpoint(main)

    _, errors = CliffordValidation().run(main)

    assert errors == []


def test_phased_xz_with_zero_x_ignores_axis_phase():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.phased_xz(0.0, math.pi / 2, math.pi / 7, q[0])

    AggressiveUnroll(main.dialects).fixpoint(main)

    _, errors = CliffordValidation().run(main)

    assert errors == []


def test_non_clifford_phased_xz_rejected():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.phased_xz(math.pi / 4, 0.0, 0.0, q[0])

    AggressiveUnroll(main.dialects).fixpoint(main)
    result = ValidationSuite([CliffordValidation]).validate(main)

    assert result.error_count() == 1
    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_symbolic_rotation_rejected():
    @squin.kernel
    def main(angle: float):
        q = squin.qalloc(1)
        squin.rx(angle, q[0])

    AggressiveUnroll(main.dialects).fixpoint(main)
    result = ValidationSuite([CliffordValidation]).validate(main)

    assert result.error_count() == 1
    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()
