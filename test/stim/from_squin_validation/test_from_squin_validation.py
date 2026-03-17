import pytest
from kirin.validation import ValidationSuite
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.stim.analysis.from_squin_validation import StimFromSquinValidation


def test_is_zero_prohibited():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        ms = squin.broadcast.measure(q)
        could_be_zero = squin.broadcast.is_zero(ms)
        squin.broadcast.reset(q)
        if could_be_zero[0]:
            squin.x(q[0])

    AggressiveUnroll(main.dialects).fixpoint(main)

    suite = ValidationSuite([StimFromSquinValidation])
    result = suite.validate(main)
    assert result.error_count() == 1

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_is_lost_prohibited():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        ms = squin.broadcast.measure(q)
        could_be_lost = squin.broadcast.is_lost(ms)
        squin.broadcast.reset(q)
        if could_be_lost[0]:
            squin.x(q[0])

    AggressiveUnroll(main.dialects).fixpoint(main)

    suite = ValidationSuite([StimFromSquinValidation])
    result = suite.validate(main)
    assert result.error_count() == 1

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_is_one_allowed():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        ms = squin.broadcast.measure(q)
        could_be_one = squin.broadcast.is_one(ms)
        squin.broadcast.reset(q)
        if could_be_one[0]:
            squin.x(q[0])

    AggressiveUnroll(main.dialects).fixpoint(main)

    suite = ValidationSuite([StimFromSquinValidation])
    result = suite.validate(main)
    assert result.error_count() == 0


def test_nested_ifelse():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        ms = squin.broadcast.measure(q)
        could_be_one = squin.broadcast.is_one(ms)
        squin.broadcast.reset(q)
        if could_be_one[0]:
            if could_be_one[1]:
                squin.x(q[1])

    AggressiveUnroll(main.dialects).fixpoint(main)

    suite = ValidationSuite([StimFromSquinValidation])
    result = suite.validate(main)
    assert result.error_count() >= 1

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_else_body():
    @squin.kernel(fold=False)
    def main():
        q = squin.qalloc(3)
        ms = squin.broadcast.measure(q)
        could_be_one = squin.broadcast.is_one(ms)
        squin.broadcast.reset(q)
        if could_be_one[0]:
            squin.x(q[0])
        else:
            squin.z(q[0])

    suite = ValidationSuite([StimFromSquinValidation])
    result = suite.validate(main)
    assert result.error_count() == 1

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_non_pauli_gate_in_ifelse():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        ms = squin.broadcast.measure(q)
        could_be_one = squin.broadcast.is_one(ms)
        squin.broadcast.reset(q)
        if could_be_one[0]:
            squin.h(q[0])

    AggressiveUnroll(main.dialects).fixpoint(main)

    suite = ValidationSuite([StimFromSquinValidation])
    result = suite.validate(main)
    assert result.error_count() == 1

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_pauli_gates_valid():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        ms = squin.broadcast.measure(q)
        could_be_one = squin.broadcast.is_one(ms)
        squin.broadcast.reset(q)
        if could_be_one[0]:
            squin.x(q[0])
        if could_be_one[1]:
            squin.y(q[1])
        if could_be_one[2]:
            squin.z(q[2])

    AggressiveUnroll(main.dialects).fixpoint(main)

    suite = ValidationSuite([StimFromSquinValidation])
    result = suite.validate(main)
    assert result.error_count() == 0


def test_multiple_errors():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        ms = squin.broadcast.measure(q)
        could_be_zero = squin.broadcast.is_zero(ms)
        could_be_one = squin.broadcast.is_one(ms)
        squin.broadcast.reset(q)

        if could_be_one[0]:
            squin.h(q[0])

        if could_be_zero[1]:
            squin.x(q[1])

    AggressiveUnroll(main.dialects).fixpoint(main)

    suite = ValidationSuite([StimFromSquinValidation])
    result = suite.validate(main)
    assert result.error_count() == 2

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_non_none_return_prohibited():
    @squin.kernel
    def main() -> int:
        q = squin.qalloc(3)
        _ms = squin.broadcast.measure(q)
        squin.broadcast.reset(q)
        return 1

    suite = ValidationSuite([StimFromSquinValidation])
    result = suite.validate(main)
    assert result.error_count() == 1

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_none_return_allowed():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        _ms = squin.broadcast.measure(q)
        squin.broadcast.reset(q)

    suite = ValidationSuite([StimFromSquinValidation])
    result = suite.validate(main)
    assert result.error_count() == 0
