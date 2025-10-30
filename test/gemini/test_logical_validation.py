import pytest
from kirin import ir

from bloqade import squin, gemini
from bloqade.types import Qubit
from bloqade.validation import KernelValidation
from bloqade.gemini.analysis import GeminiLogicalValidationAnalysis
from bloqade.validation.kernel_validation import ValidationErrorGroup


def test_if_stmt_invalid():
    @gemini.logical(verify=False)
    def main():
        q = squin.qalloc(3)

        squin.h(q[0])

        for i in range(10):
            squin.x(q[1])

        m = squin.qubit.measure(q[1])

        q2 = squin.qalloc(5)
        squin.x(q2[0])

        if m:
            squin.x(q[1])

        m2 = squin.qubit.measure(q[2])
        if m2:
            squin.y(q[2])

    frame, _ = GeminiLogicalValidationAnalysis(main.dialects).run_analysis(
        main, no_raise=False
    )

    main.print(analysis=frame.entries)

    validator = KernelValidation(GeminiLogicalValidationAnalysis)

    with pytest.raises(ValidationErrorGroup):
        validator.run(main)


def test_for_loop():

    @gemini.logical
    def valid_loop():
        q = squin.qalloc(3)

        for i in range(3):
            squin.x(q[i])

    valid_loop.print()

    with pytest.raises(ir.ValidationError):

        @gemini.logical
        def invalid_loop(n: int):
            q = squin.qalloc(3)

            for i in range(n):
                squin.x(q[i])

        invalid_loop.print()


def test_func():
    @gemini.logical
    def sub_kernel(q: Qubit):
        squin.x(q)

    @gemini.logical
    def main():
        q = squin.qalloc(3)
        sub_kernel(q[0])

    main.print()

    with pytest.raises(ValidationErrorGroup):

        @gemini.logical(inline=False)
        def invalid():
            q = squin.qalloc(3)
            sub_kernel(q[0])


def test_clifford_gates():
    @gemini.logical
    def main():
        q = squin.qalloc(2)
        squin.u3(0.123, 0.253, 1.2, q[0])

        squin.h(q[0])
        squin.cx(q[0], q[1])

    with pytest.raises(ir.ValidationError):

        @gemini.logical(no_raise=False)
        def invalid():
            q = squin.qalloc(2)

            squin.h(q[0])
            squin.cx(q[0], q[1])
            squin.u3(0.123, 0.253, 1.2, q[0])

        frame, _ = GeminiLogicalValidationAnalysis(invalid.dialects).run_analysis(
            invalid, no_raise=False
        )

        invalid.print(analysis=frame.entries)


def test_multiple_errors():
    did_error = False
    try:

        @gemini.logical
        def main(n: int):
            q = squin.qalloc(3)
            m = squin.qubit.measure(q[0])
            squin.x(q[1])
            if m:
                squin.x(q[0])

            for k in range(n):
                squin.h(q[k])

            squin.u3(0.1, 0.2, 0.3, q[1])

    except ValidationErrorGroup as e:
        did_error = True
        assert len(e.errors) == 3

    assert did_error
