from typing import List, TypeVar

from kirin.analysis import ForwardFrame

from bloqade.analysis.validation.nocloning.lattice import May, Must

T = TypeVar("T", bound=Must | May)


def collect_errors(frame: ForwardFrame[T], typ: type[T]) -> List[str]:
    """Collect individual violation strings from all QubitValidation entries of type `typ`."""
    violations: List[str] = []
    for validation_val in frame.entries.values():
        if isinstance(validation_val, typ):
            for v in validation_val.violations:
                violations.append(v)
    return violations


def collect_must_errors(frame):
    return collect_errors(frame, Must)


def collect_may_errors(frame):
    return collect_errors(frame, May)
