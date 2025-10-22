from abc import ABC
from typing import Iterable
from dataclasses import field, dataclass

from kirin import ir
from kirin.analysis import ForwardExtra, ForwardFrame

from .lattice import Error, ErrorType


@dataclass
class ValidationFrame(ForwardFrame[ErrorType]):
    # NOTE: cannot be set[Error] since that's not hashable
    errors: list[Error] = field(default_factory=list)
    """List of all ecnountered errors."""


@dataclass
class ValidationAnalysis(ForwardExtra[ValidationFrame, ErrorType], ABC):
    """Analysis pass that indicates errors in the IR according to the respective method tables.

    If you need to implement validation for a dialect shared by many groups (for example, if you need to ascertain if statements have a specific form)
    you'll need to inherit from this class.
    """

    lattice = ErrorType

    def run_method(self, method: ir.Method, args: tuple[ErrorType, ...]):
        return self.run_callable(method.code, (self.lattice.top(),) + args)

    def eval_stmt_fallback(self, frame: ValidationFrame, stmt: ir.Statement):
        # NOTE: default to no errors
        return (self.lattice.top(),)

    def set_values(
        self,
        frame: ValidationFrame,
        ssa: Iterable[ir.SSAValue],
        results: Iterable[ErrorType],
    ):
        """Set the abstract values for the given SSA values in the frame.

        This method is overridden to explicitly collect all errors we found in the
        additional field of the frame. That also includes statements that don't
        have an associated `ResultValue`.
        """

        ssa_value_list = list(ssa)
        number_of_ssa_values = len(ssa_value_list)
        for i, result in enumerate(results):
            if isinstance(result, Error):
                frame.errors.append(result)

            if i < number_of_ssa_values:
                ssa_value = ssa_value_list[i]

                if ssa_value in frame.entries:
                    frame.entries[ssa_value] = frame.entries[ssa_value].join(result)
                else:
                    frame.entries[ssa_value] = result

    def initialize_frame(
        self, code: ir.Statement, *, has_parent_access: bool = False
    ) -> ValidationFrame:
        return ValidationFrame(code, has_parent_access=has_parent_access)
