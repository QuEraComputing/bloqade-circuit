from kirin import ir
from kirin.analysis import Forward, ForwardFrame

from .lattice import ErrorType


class GeminiLogicalValidationAnalysis(Forward[ErrorType]):
    keys = ["gemini.validate.logical"]
    lattice = ErrorType

    has_allocated_qubits: bool = False

    def run_method(self, method: ir.Method, args: tuple[ErrorType, ...]):
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)

    def eval_stmt_fallback(self, frame: ForwardFrame[ErrorType], stmt: ir.Statement):
        return (self.lattice.top(),)
