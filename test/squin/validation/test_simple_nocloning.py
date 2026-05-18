import pytest
from kirin.validation import ValidationSuite
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.analysis.validation.simple_nocloning import FlatKernelNoCloningValidation


def test_gates():

    @squin.kernel
    def bad_kernel():
        q = squin.qalloc(3)
        squin.broadcast.x([q[0], q[1], q[0]])
        squin.broadcast.rx(0.123, [q[1], q[1]])
        squin.cx(q[2], q[2])

    AggressiveUnroll(bad_kernel.dialects).fixpoint(bad_kernel)

    _, errors = FlatKernelNoCloningValidation().run(bad_kernel)
    assert len(errors) == 3


def test_noise():
    @squin.kernel
    def bad_kernel():
        q = squin.qalloc(3)
        squin.broadcast.depolarize(0.1, [q[0], q[0]])
        squin.broadcast.depolarize2(0.1, [q[0]], [q[0]])

    AggressiveUnroll(bad_kernel.dialects).fixpoint(bad_kernel)

    validation_suite = ValidationSuite([FlatKernelNoCloningValidation])
    result = validation_suite.validate(bad_kernel)
    assert result.error_count() == 2

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_correlated_loss():
    @squin.kernel
    def bad_kernel():
        q = squin.qalloc(3)
        squin.broadcast.correlated_qubit_loss(0.1, [[q[0], q[1]], [q[1], q[2]]])

    AggressiveUnroll(bad_kernel.dialects).fixpoint(bad_kernel)

    validation_suite = ValidationSuite([FlatKernelNoCloningValidation])
    result = validation_suite.validate(bad_kernel)
    assert result.error_count() == 1

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()
