from kirin import ir, passes
from kirin.prelude import structural_no_opt
from kirin.dialects import ilist
from kirin.rewrite.walk import Walk

from . import op, wire, qubit
from .rewrite.measure_desugar import MeasureDesugarRule
from .op.rewrite import PyMultToSquinMult


@ir.dialect_group(structural_no_opt.union([op, qubit]))
def kernel(self):
    fold_pass = passes.Fold(self)
    typeinfer_pass = passes.TypeInfer(self)
    ilist_desugar_pass = ilist.IListDesugar(self)
    measure_desugar_pass = Walk(MeasureDesugarRule())
    py_mult_to_mult_pass = PyMultToSquinMult(self)

    def run_pass(method: ir.Method, *, fold=True, typeinfer=True):
        method.verify()
        if fold:
            fold_pass.fixpoint(method)

        if typeinfer:
            typeinfer_pass(method)
            measure_desugar_pass.rewrite(method.code)

        ilist_desugar_pass(method)
        py_mult_to_mult_pass(method)

        if typeinfer:
            typeinfer_pass(method)  # fix types after desugaring
            method.verify_type()

    return run_pass


@ir.dialect_group(structural_no_opt.union([op, wire]))
def wired(self):
    def run_pass(method):
        pass

    return run_pass
