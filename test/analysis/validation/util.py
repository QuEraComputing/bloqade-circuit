from typing import TypeVar

from kirin.analysis import ForwardFrame

from bloqade.analysis.validation.nocloning.lattice import QubitValidation

T = TypeVar("T", bound=QubitValidation)


def collect_validation_errors(
    frame: ForwardFrame[QubitValidation], typ: type[T]
) -> list[T]:
    return [
        validation_errors
        for validation_errors in frame.entries.values()
        if isinstance(validation_errors, typ) and len(validation_errors.violations) > 0
    ]
