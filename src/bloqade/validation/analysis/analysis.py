from abc import ABC
from dataclasses import field, dataclass

from kirin import ir
from kirin.analysis import ForwardExtra, ForwardFrame

from .lattice import ErrorType


@dataclass
class ValidationFrame(ForwardFrame[ErrorType]):
    # NOTE: cannot be set[Error] since that's not hashable
    errors: list[ir.ValidationError] = field(default_factory=list)
    """List of all ecnountered errors.

    Append a `kirin.ir.ValidationError` to this list in the method implementation
    in order for it to get picked up by the `KernelValidation` run.
    """


@dataclass
class ValidationAnalysis(ForwardExtra[ValidationFrame, ErrorType], ABC):
    """Analysis pass that indicates errors in the IR according to the respective method tables.

    If you need to implement validation for a dialect shared by many groups (for example, if you need to ascertain if statements have a specific form)
    you'll need to inherit from this class.
    """

    lattice = ErrorType

    def eval_fallback(self, frame: ValidationFrame, node: ir.Statement):
        # NOTE: default to no errors
        return tuple(self.lattice.top() for _ in node.results)

    def initialize_frame(
        self, node: ir.Statement, *, has_parent_access: bool = False
    ) -> ValidationFrame:
        return ValidationFrame(node, has_parent_access=has_parent_access)

    def method_self(self, method: ir.Method) -> ErrorType:
        return self.lattice.top()
