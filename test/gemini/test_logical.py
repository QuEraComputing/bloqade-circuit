import pytest
from kirin import ir

from bloqade import squin, gemini
from bloqade.gemini.analysis import GeminiLogicalValidationAnalysis
from bloqade.gemini.validation.logical import KernelValidation


def test_if_stmt_invalid():
    @gemini.logical(verify=False)
    def main():
        q = squin.qubit.new(3)

        squin.h(q[0])

        for i in range(10):
            squin.x(q[1])

        m = squin.qubit.measure(q[1])

        q2 = squin.qubit.new(5)
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

    with pytest.raises(ir.ValidationError):
        validator.run(main)
