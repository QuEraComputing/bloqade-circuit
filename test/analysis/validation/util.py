from typing import List

from kirin.analysis import ForwardFrame

from bloqade.analysis.validation.nocloning.lattice import QubitValidation


def collect_validation_errors(
    frame: ForwardFrame[QubitValidation], typ: type[QubitValidation]
) -> List[str]:
    """Collect individual violation strings from all QubitValidation entries of type `typ`."""
    violations: List[str] = []
    for validation_val in frame.entries.values():
        if isinstance(validation_val, typ):
            for v in getattr(validation_val, "violations", ()):
                violations.append(v)
    return violations
