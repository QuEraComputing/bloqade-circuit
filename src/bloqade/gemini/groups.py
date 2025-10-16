from kirin import ir
from kirin.prelude import structural_no_opt
from kirin.dialects import py, func, ilist

from bloqade.squin import gate, qubit

# from .passes import ValidateGeminiLogical
# from .analysis import GeminiLogicalValidationAnalysis
# from .analysis.logical_validation.analysis import ValidateInterpreter


@ir.dialect_group(structural_no_opt.union([gate, py.constant, qubit, func, ilist]))
def logical(self):

    def run_pass(mt: ir.Method, *, validate=True):
        if validate:
            # GeminiLogicalValidationAnalysis(mt.dialects).run_analysis(mt, no_raise=False)
            # ValidateInterpreter(mt.dialects).run(mt, ())
            mt.verify()

    return run_pass
