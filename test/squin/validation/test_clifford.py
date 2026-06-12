import math

import pytest
from kirin.validation import ValidationSuite
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.stim.passes.flatten import Flatten
from bloqade.squin.analysis.validation import CliffordValidation


def _validate(kernel):
    AggressiveUnroll(kernel.dialects).fixpoint(kernel)
    _, errors = CliffordValidation().run(kernel)
    return errors


def test_clifford_kernel_passes():
    @squin.kernel
    def main():
        q = squin.qalloc(4)
        squin.h(q[0])
        for i in range(3):
            squin.cx(q[i], q[i + 1])

    assert len(_validate(main)) == 0


def test_named_clifford_gates_pass():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.x(q[0])
        squin.y(q[0])
        squin.z(q[0])
        squin.h(q[0])
        squin.s(q[0])
        squin.sqrt_x(q[0])
        squin.sqrt_y(q[0])
        squin.cx(q[0], q[1])
        squin.cy(q[0], q[1])
        squin.cz(q[0], q[1])

    assert len(_validate(main)) == 0


def test_t_gate_fails():
    @squin.kernel
    def main():
        q = squin.qalloc(4)
        squin.h(q[0])
        for i in range(3):
            squin.t(q[i])
            squin.cx(q[i], q[i + 1])

    assert len(_validate(main)) == 3


def test_clifford_angle_rotations_pass():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.rx(math.pi / 2, q[0])
        squin.ry(math.pi, q[0])
        squin.rz(3 * math.pi / 2, q[0])

    assert len(_validate(main)) == 0


def test_non_clifford_angle_rotation_fails():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.rz(0.1, q[0])

    assert len(_validate(main)) == 1


def test_clifford_u3_passes():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.u3(math.pi / 2, 0.0, math.pi, q[0])

    assert len(_validate(main)) == 0


def test_non_clifford_u3_fails():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.u3(0.1, 0.2, 0.3, q[0])

    assert len(_validate(main)) == 1


def test_phased_xz_fails():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.phased_xz(0.25, 0.5, 0.0, q[0])

    assert len(_validate(main)) == 1


def test_matches_squin_to_stim_pipeline():
    # Mirrors how SquinToStimPass uses validation: Flatten first, then validate.
    @squin.kernel
    def main():
        q = squin.qalloc(4)
        squin.h(q[0])
        for i in range(3):
            squin.t(q[i])
            squin.cx(q[i], q[i + 1])

    Flatten(dialects=main.dialects).fixpoint(main)
    _, errors = CliffordValidation().run(main)
    assert len(errors) == 3


def test_validation_suite_raises():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.t(q[0])
        squin.cx(q[0], q[1])

    AggressiveUnroll(main.dialects).fixpoint(main)

    result = ValidationSuite([CliffordValidation]).validate(main)
    assert result.error_count() == 1

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()
