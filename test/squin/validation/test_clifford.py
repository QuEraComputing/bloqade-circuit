import pytest
from kirin.validation import ValidationSuite
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.analysis.validation.clifford import CliffordValidation


def test_clifford_kernel_passes():
    @squin.kernel
    def main_clifford():
        q = squin.qalloc(4)
        squin.h(q[0])
        for i in range(3):
            squin.cx(q[i], q[i + 1])

    AggressiveUnroll(main_clifford.dialects).fixpoint(main_clifford)

    _, errors = CliffordValidation().run(main_clifford)
    assert len(errors) == 0


def test_non_clifford_t_gate_fails():
    @squin.kernel
    def main_nonclifford():
        q = squin.qalloc(4)
        squin.h(q[0])
        for i in range(3):
            squin.t(q[i])
            squin.cx(q[i], q[i + 1])

    AggressiveUnroll(main_nonclifford.dialects).fixpoint(main_nonclifford)

    suite = ValidationSuite([CliffordValidation])
    result = suite.validate(main_nonclifford)
    assert result.error_count() == 3

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_non_clifford_rotation_and_u3_fail():
    @squin.kernel
    def main_nonclifford():
        q = squin.qalloc(3)
        squin.rx(0.125, q[0])
        squin.broadcast.rz(0.25, [q[1], q[2]])
        squin.u3(0.0, 0.0, 0.125, q[0])

    AggressiveUnroll(main_nonclifford.dialects).fixpoint(main_nonclifford)

    _, errors = CliffordValidation().run(main_nonclifford)
    assert len(errors) == 3
    assert all("not a Clifford gate" in str(error) for error in errors)


def test_clifford_adjoint_gates_pass():
    @squin.kernel
    def main_clifford():
        q = squin.qalloc(3)
        squin.s_adj(q[0])
        squin.sqrt_x_adj(q[1])
        squin.sqrt_y_adj(q[2])
        squin.cy(q[0], q[1])
        squin.cz(q[1], q[2])

    AggressiveUnroll(main_clifford.dialects).fixpoint(main_clifford)

    result = ValidationSuite([CliffordValidation]).validate(main_clifford)
    assert result.error_count() == 0
