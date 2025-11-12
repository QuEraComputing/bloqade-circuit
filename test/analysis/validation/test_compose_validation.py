import pytest
from kirin.validation.validationpass import ValidationSuite

from bloqade import squin
from bloqade.analysis.validation.nocloning import NoCloningValidation


def test_validation_suite():
    @squin.kernel
    def bad_kernel(a: int):
        q = squin.qalloc(2)
        squin.cx(q[0], q[0])  # definite cloning error
        squin.cx(q[a], q[1])  # potential cloning error

    # Running no-cloning validation multiple times
    suite = ValidationSuite(
        [
            NoCloningValidation,
            NoCloningValidation,
            NoCloningValidation,
        ]
    )
    result = suite.validate(bad_kernel)

    assert not result.is_valid()
    assert (
        result.error_count() == 2
    )  #  Report 2 errors, even when validated multiple times
    print(result.format_errors())
    with pytest.raises(Exception):
        result.raise_if_invalid()


def test_validation_suite2():
    @squin.kernel
    def good_kernel():
        q = squin.qalloc(2)
        squin.cx(q[0], q[1])

    suite = ValidationSuite(
        [
            NoCloningValidation,
        ],
        fail_fast=True,
    )
    result = suite.validate(good_kernel)

    assert result.is_valid()
    assert result.error_count() == 0
    print(result.format_errors())
    result.raise_if_invalid()
