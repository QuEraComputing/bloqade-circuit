from kirin import ir

from bloqade.validation.analysis import ValidationFrame, ValidationAnalysis
from bloqade.validation.analysis.lattice import ErrorType


class GeminiLogicalValidationAnalysis(ValidationAnalysis):
    keys = ["gemini.validate.logical"]
    lattice = ErrorType

    has_allocated_qubits: bool = False

    def run_method(self, method: ir.Method, args: tuple[ErrorType, ...]):
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)

    def eval_stmt_fallback(self, frame: ValidationFrame, stmt: ir.Statement):
        return (self.lattice.top(),)
