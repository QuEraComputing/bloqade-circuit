import sys
import itertools
from dataclasses import dataclass

from kirin import ir, exception
from rich.console import Console

from .analysis import ValidationFrame, ValidationAnalysis
from .analysis.lattice import Error, ErrorType


class ValidationErrorGroup(BaseException):
    def __init__(self, *args: object, errors=[]) -> None:
        super().__init__(*args)
        self.errors = errors


# TODO: this overrides kirin's exception handler and should be upstreamed
def exception_handler(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, ValidationErrorGroup):
        console = Console(force_terminal=True)
        for i, err in enumerate(exc_value.errors):
            with console.capture() as capture:
                console.print(f"==== Error {i} ====")
                console.print(f"[bold red]{type(err).__name__}:[/bold red]", end="")
            print(capture.get(), *err.args, file=sys.stderr)
            if err.source:
                print("Source Traceback:", file=sys.stderr)
                print(err.hint(), file=sys.stderr, end="")
        console.print("=" * 40)
        console.print(
            "[bold red]Kernel validation failed:[/bold red] There were multiple errors encountered during validation, see above"
        )
        return

    return exception.exception_handler(exc_type, exc_value, exc_tb)


sys.excepthook = exception_handler


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
        elif len(errors) == 1:
            raise errors[0]
        else:
            raise ValidationErrorGroup(errors=errors)

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
