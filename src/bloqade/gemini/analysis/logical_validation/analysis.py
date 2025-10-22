from kirin import ir

from bloqade import squin
from bloqade.validation.analysis import ValidationFrame, ValidationAnalysis


class GeminiLogicalValidationAnalysis(ValidationAnalysis):
    keys = ["gemini.validate.logical"]

    first_gate = True

    def eval_stmt_fallback(self, frame: ValidationFrame, stmt: ir.Statement):

        if isinstance(stmt, squin.gate.stmts.Gate):
            # NOTE: to validate that only the first encountered gate can be non-Clifford, we need to track this here
            self.first_gate = False

        return (self.lattice.top(),)
