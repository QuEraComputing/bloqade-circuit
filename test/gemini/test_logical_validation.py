import pytest
from kirin.validation import ValidationSuite
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin, gemini
from bloqade.types import Qubit
from bloqade.gemini.analysis.logical_validation.analysis import (
    GeminiLogicalValidation,
    _GeminiLogicalValidationAnalysis,
)
from bloqade.gemini.analysis.measurement_validation.analysis import (
    GeminiTerminalMeasurementValidation,
)


def test_if_stmt_invalid():
    @gemini.logical.kernel(verify=False)
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

    frame, _ = _GeminiLogicalValidationAnalysis(main.dialects).run_no_raise(main)

    main.print(analysis=frame.entries)

    validator = ValidationSuite([GeminiLogicalValidation])
    validation_result = validator.validate(main)

    with pytest.raises(ValidationErrorGroup):
        validation_result.raise_if_invalid()


def test_for_loop():

    @gemini.logical.kernel
    def valid_loop():
        q = squin.qalloc(3)

        for i in range(3):
            squin.x(q[i])

    valid_loop.print()

    with pytest.raises(ValidationErrorGroup):

        @gemini.logical.kernel
        def invalid_loop(n: int):
            q = squin.qalloc(3)

            for i in range(n):
                squin.x(q[i])

        invalid_loop.print()


def test_func():
    @gemini.logical.kernel
    def sub_kernel(q: Qubit):
        squin.x(q)

    @gemini.logical.kernel
    def main():
        q = squin.qalloc(3)
        sub_kernel(q[0])

    main.print()

    with pytest.raises(ValidationErrorGroup):

        @gemini.logical.kernel(inline=False)
        def invalid():
            q = squin.qalloc(3)
            sub_kernel(q[0])


def test_clifford_gates():
    @gemini.logical.kernel
    def main():
        q = squin.qalloc(2)
        squin.u3(0.123, 0.253, 1.2, q[0])

        squin.h(q[0])
        squin.cx(q[0], q[1])

    with pytest.raises(ValidationErrorGroup):

        @gemini.logical.kernel(no_raise=False)
        def invalid():
            q = squin.qalloc(2)

            squin.h(q[0])
            squin.cx(q[0], q[1])
            squin.u3(0.123, 0.253, 1.2, q[0])

        frame, _ = _GeminiLogicalValidationAnalysis(invalid.dialects).run_no_raise(
            invalid
        )

        invalid.print(analysis=frame.entries)


def test_qalloc_and_terminal_measure_type_valid():

    @gemini.logical.kernel(aggressive_unroll=True)
    def main():
        q = squin.qalloc(3)
        gemini.logical.terminal_measure(q)

    validator = ValidationSuite([GeminiTerminalMeasurementValidation])
    validation_result = validator.validate(main)

    validation_result.raise_if_invalid()


def test_terminal_measurement():

    @gemini.logical.kernel(
        verify=False, no_raise=False, aggressive_unroll=True, typeinfer=True
    )
    def not_all_qubits_consumed():
        qs = squin.qalloc(3)
        sub_qs = qs[0:2]
        tm = gemini.logical.terminal_measure(sub_qs)
        return tm

    validator = ValidationSuite([GeminiTerminalMeasurementValidation])
    validation_result = validator.validate(not_all_qubits_consumed)

    with pytest.raises(ValidationErrorGroup):
        validation_result.raise_if_invalid()

    @gemini.logical.kernel(verify=False)
    def terminal_measure_kernel(q):
        return gemini.logical.terminal_measure(q)

    @gemini.logical.kernel(
        verify=False, no_raise=False, aggressive_unroll=True, typeinfer=True
    )
    def terminal_measure_in_kernel():
        q = squin.qalloc(10)
        sub_qs = q[:2]
        m = terminal_measure_kernel(sub_qs)
        return m

    validator = ValidationSuite([GeminiTerminalMeasurementValidation])
    validation_result = validator.validate(terminal_measure_in_kernel)

    with pytest.raises(ValidationErrorGroup):
        validation_result.raise_if_invalid()


def test_multiple_errors():
    did_error = False

    try:

        @gemini.logical.kernel
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
        assert len(e.errors) == 4

    assert did_error
