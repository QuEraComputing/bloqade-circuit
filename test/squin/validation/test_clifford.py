import pytest
from kirin.validation import ValidationSuite
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.squin.analysis.validation import CliffordValidation


def test_clifford_kernel_passes():
    @squin.kernel
    def main():
        q = squin.qalloc(4)
        squin.x(q[0])
        squin.y(q[1])
        squin.z(q[2])
        squin.h(q[3])
        squin.s(q[0])
        squin.s_adj(q[1])
        squin.sqrt_x(q[2])
        squin.sqrt_x_adj(q[3])
        squin.sqrt_y(q[0])
        squin.sqrt_y_adj(q[1])
        squin.cx(q[0], q[1])
        squin.cy(q[1], q[2])
        squin.cz(q[2], q[3])

    result = ValidationSuite([CliffordValidation]).validate(main)
    assert result.error_count() == 0


def test_non_clifford_kernel_fails():
    @squin.kernel
    def main():
        q = squin.qalloc(5)
        squin.t(q[0])
        squin.t_adj(q[1])
        squin.rx(0.25, q[2])
        squin.ry(0.5, q[3])
        squin.rz(0.75, q[4])

    result = ValidationSuite([CliffordValidation]).validate(main)
    assert result.error_count() == 5

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_u3_and_phased_xz_fail():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.u3(0.1, 0.2, 0.3, q[0])
        squin.phased_xz(0.1, 0.2, 0.3, q[1])

    _, errors = CliffordValidation().run(main)
    assert len(errors) == 2
    assert {type(error.node).__name__ for error in errors} == {"U3", "PhasedXZ"}
