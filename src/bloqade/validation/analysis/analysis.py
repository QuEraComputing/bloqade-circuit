from abc import ABC
from typing import Iterable
from dataclasses import field, dataclass

from kirin import ir
from kirin.interp import AbstractFrame
from kirin.analysis import Forward, ForwardFrame

from .lattice import ErrorType

ValidationFrame = ForwardFrame[ErrorType]


@dataclass
class ValidationAnalysis(Forward[ErrorType], ABC):
    """Analysis pass that indicates errors in the IR according to the respective method tables.

    If you need to implement validation for a dialect shared by many groups (for example, if you need to ascertain if statements have a specific form)
    you'll need to inherit from this class.
    """

    lattice = ErrorType

    additional_errors: list[ErrorType] = field(default_factory=list)
    """List to store return values that are not associated with an SSA Value (e.g. when the statement has no ResultValue)"""

    def run_method(self, method: ir.Method, args: tuple[ErrorType, ...]):
        return self.run_callable(method.code, (self.lattice.top(),) + args)

    def eval_stmt_fallback(self, frame: ValidationFrame, stmt: ir.Statement):
        # NOTE: default to no errors
        return (self.lattice.top(),)

    def set_values(
        self,
        frame: AbstractFrame[ErrorType],
        ssa: Iterable[ir.SSAValue],
        results: Iterable[ErrorType],
    ):
        """Set the abstract values for the given SSA values in the frame.

        This method is overridden to account for additional errors we may
        encounter when they are not associated to an SSA Value.
        """

        number_of_ssa_values = 0
        for ssa_value, result in zip(ssa, results):
            number_of_ssa_values += 1
            if ssa_value in frame.entries:
                frame.entries[ssa_value] = frame.entries[ssa_value].join(result)
            else:
                frame.entries[ssa_value] = result

        if isinstance(results, tuple):
            # NOTE: usually what we have
            self.additional_errors.extend(results[number_of_ssa_values + 1 :])

        for i, result in enumerate(results):
            # NOTE: only sure-fire way I found to get remaining values from an Iterable
            if i <= number_of_ssa_values:
                continue

            self.additional_errors.append(result)
