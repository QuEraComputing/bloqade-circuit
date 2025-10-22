from abc import ABC

from kirin import ir
from kirin.analysis import Forward, ForwardFrame

from .lattice import ErrorType

ValidationFrame = ForwardFrame[ErrorType]


class ValidationAnalysis(Forward[ErrorType], ABC):
    """Analysis pass that indicates errors in the IR according to the respective method tables.

    If you need to implement validation for a dialect shared by many groups (for example, if you need to ascertain if statements have a specific form)
    you'll need to inherit from this class.
    """

    lattice = ErrorType

    def run_method(self, method: ir.Method, args: tuple[ErrorType, ...]):
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)

    def eval_stmt_fallback(self, frame: ValidationFrame, stmt: ir.Statement):
        # NOTE: default to no errors
        return (self.lattice.top(),)
