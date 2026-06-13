import pytest
from kirin.validation import ValidationSuite
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.squin.analysis.validation import CliffordValidation


def test_clifford_kernel_is_valid():
    @squin.kernel
    def main_clifford():
        q = squin.qalloc(4)
        squin.h(q[0])
        for i in range(3):
            squin.cx(q[i], q[i + 1])

    _, errors = CliffordValidation().run(main_clifford)
    assert len(errors) == 0


def test_non_clifford_kernel_is_invalid():
    @squin.kernel
    def main_nonclifford():
        q = squin.qalloc(4)
        squin.h(q[0])
        for i in range(3):
            squin.t(q[i])
            squin.cx(q[i], q[i + 1])

    _, errors = CliffordValidation().run(main_nonclifford)
    assert len(errors) > 0
    assert "T" in str(errors[0])


def test_validation_suite_raises_for_non_clifford_gate():
    @squin.kernel
    def main_nonclifford():
        q = squin.qalloc(1)
        squin.rx(0.25, q[0])

    suite = ValidationSuite([CliffordValidation])
    result = suite.validate(main_nonclifford)
    assert result.error_count() == 1

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_clifford_adjoint_gates_are_valid():
    @squin.kernel
    def main_clifford():
        q = squin.qalloc(3)
        squin.s_adj(q[0])
        squin.sqrt_x_adj(q[1])
        squin.sqrt_y_adj(q[2])

    _, errors = CliffordValidation().run(main_clifford)
    assert len(errors) == 0
