from kirin import ir, passes
from kirin.prelude import structural_no_opt
from kirin.rewrite import Walk, Chain
from kirin.dialects import ilist

from . import gate, noise, qubit
from .rewrite.desugar import MeasureDesugarRule


@ir.dialect_group(structural_no_opt.union([qubit, noise, gate]))
def kernel(self):
    fold_pass = passes.Fold(self)
    typeinfer_pass = passes.TypeInfer(self)
    ilist_desugar_pass = ilist.IListDesugar(self)
    desugar_pass = Walk(Chain(MeasureDesugarRule()))

    def run_pass(method: ir.Method, *, fold=True, typeinfer=True):
        method.verify()
        if fold:
            fold_pass.fixpoint(method)

        if typeinfer:
            typeinfer_pass(method)
            desugar_pass.rewrite(method.code)

        ilist_desugar_pass(method)

        if typeinfer:
            typeinfer_pass(method)  # fix types after desugaring
            method.verify_type()

    return run_pass
