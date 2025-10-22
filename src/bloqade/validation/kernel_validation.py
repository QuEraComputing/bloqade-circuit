import itertools
from dataclasses import dataclass

from kirin import ir

from .analysis import ValidationFrame, ValidationAnalysis
from .analysis.lattice import Error, ErrorType


@dataclass
class KernelValidation:
    validation_analysis_cls: type[ValidationAnalysis]

    def run(self, mt: ir.Method, **kwargs) -> None:
        validation_analysis = self.validation_analysis_cls(mt.dialects)
        validation_frame, _ = validation_analysis.run_analysis(mt, **kwargs)

        errors = self.get_exceptions(
            mt, validation_frame, validation_analysis.additional_errors
        )

        if len(errors) == 0:
            # Valid program
            return

        # TODO: Make something similar to an ExceptionGroup that pretty-prints ValidationErrors
        raise errors[0]

    def get_exceptions(
        self,
        mt: ir.Method,
        validation_frame: ValidationFrame,
        additional_errors: list[ErrorType],
    ):
        errors = []
        for value in itertools.chain(
            validation_frame.entries.values(), additional_errors
        ):
            if not isinstance(value, Error):
                continue

            error = ir.ValidationError(value.stmt, value.msg, help=value.help)
            error.attach(mt)

            errors.append(error)

        return errors
