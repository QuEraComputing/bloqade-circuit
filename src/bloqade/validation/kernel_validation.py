import sys
from dataclasses import dataclass

from kirin import ir, exception
from rich.console import Console

from .analysis import ValidationAnalysis


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
    """Validate a kernel according to a `ValidationAnalysis`.

    This is a simple wrapper around the analysis that runs the analysis, checks
    the `ValidationFrame` for errors and throws them if there are any.
    """

    validation_analysis_cls: type[ValidationAnalysis]
    """The analysis that you want to run in order to validate the kernel."""

    def run(self, mt: ir.Method, **kwargs) -> None:
        validation_analysis = self.validation_analysis_cls(mt.dialects)
        validation_frame, _ = validation_analysis.run_analysis(mt, **kwargs)

        errors = validation_frame.errors

        if len(errors) == 0:
            # Valid program
            return
        elif len(errors) == 1:
            raise errors[0]
        else:
            raise ValidationErrorGroup(errors=errors)
