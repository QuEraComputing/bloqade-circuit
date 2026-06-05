import pytest
from kirin.validation import ValidationSuite
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.squin.analysis.validation import CliffordValidation


def test_clifford_kernel_passes():
    @squin.kernel
    def main():
        q = squin.qalloc(4)
        squin.h(q[0])
        squin.s(q[1])
        squin.s_adj(q[1])
        squin.sqrt_x(q[2])
        squin.sqrt_y_adj(q[3])

        for i in range(3):
            squin.cx(q[i], q[i + 1])

    AggressiveUnroll(main.dialects).fixpoint(main)

    _, errors = CliffordValidation().run(main)
    assert len(errors) == 0


def test_issue_example_runs_without_manual_unroll():
    @squin.kernel
    def main_clifford():
        q = squin.qalloc(4)
        squin.h(q[0])
        for i in range(3):
            squin.cx(q[i], q[i + 1])

    @squin.kernel
    def main_nonclifford():
        q = squin.qalloc(4)
        squin.h(q[0])
        for i in range(3):
            squin.t(q[i])
            squin.cx(q[i], q[i + 1])

    assert len(CliffordValidation().run(main_clifford)[1]) == 0
    assert len(CliffordValidation().run(main_nonclifford)[1]) > 0


def test_non_clifford_t_gates_fail():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.t(q[0])
        squin.t_adj(q[1])

    AggressiveUnroll(main.dialects).fixpoint(main)

    validation_suite = ValidationSuite([CliffordValidation])
    result = validation_suite.validate(main)
    assert result.error_count() == 2

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_parameterized_gates_fail():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        squin.rx(0.125, q[0])
        squin.ry(0.125, q[1])
        squin.rz(0.125, q[2])
        squin.u3(0.1, 0.2, 0.3, q[0])
        squin.phased_xz(0.1, 0.2, 0.3, q[1])

    AggressiveUnroll(main.dialects).fixpoint(main)

    validation_suite = ValidationSuite([CliffordValidation])
    result = validation_suite.validate(main)
    assert result.error_count() == 5

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()
