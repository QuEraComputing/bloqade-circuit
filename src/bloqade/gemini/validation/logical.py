from dataclasses import dataclass

from kirin import ir
from kirin.analysis import Forward, ForwardFrame

from ..analysis.logical_validation.lattice import Error


@dataclass
class KernelValidation:
    validation_analysis_cls: type[Forward]

    def run(self, mt: ir.Method, **kwargs) -> None:
        validation_analysis = self.validation_analysis_cls(mt.dialects)
        validation_frame, _ = validation_analysis.run_analysis(mt, **kwargs)

        errors = self.get_exceptions(mt, validation_frame)

        if len(errors) == 0:
            # Valid program
            return

        # TODO: Make something similar to an ExceptionGroup that pretty-prints ValidationErrors
        raise errors[0]

    def get_exceptions(self, mt: ir.Method, validation_frame: ForwardFrame):
        errors = []
        for value in validation_frame.entries.values():
            if not isinstance(value, Error):
                continue

            if isinstance(value.error, ir.ValidationError):
                value.error.attach(mt)

            errors.append(value.error)

        return errors
