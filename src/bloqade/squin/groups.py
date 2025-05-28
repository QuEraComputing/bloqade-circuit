from kirin import ir, passes
from kirin.prelude import structural_no_opt
from kirin.rewrite import Walk, Chain
from kirin.dialects import ilist

from . import op, wire, noise, qubit
from .op.rewrite import PyMultToSquinMult
from .rewrite.desugar import ApplyDesugarRule, MeasureDesugarRule


@ir.dialect_group(structural_no_opt.union([op, qubit, noise]))
def kernel(self):
    fold_pass = passes.Fold(self)
    typeinfer_pass = passes.TypeInfer(self)
    ilist_desugar_pass = ilist.IListDesugar(self)
    desugar_pass = Walk(Chain(MeasureDesugarRule(), ApplyDesugarRule()))
    py_mult_to_mult_pass = PyMultToSquinMult(self)

    def run_pass(method: ir.Method, *, fold=True, typeinfer=True):
        method.verify()
        if fold:
            fold_pass.fixpoint(method)

        py_mult_to_mult_pass(method)

        if typeinfer:
            typeinfer_pass(method)
            desugar_pass.rewrite(method.code)

        ilist_desugar_pass(method)

        if typeinfer:
            typeinfer_pass(method)  # fix types after desugaring
            method.verify_type()

    return run_pass


@ir.dialect_group(structural_no_opt.union([op, wire, noise]))
def wired(self):
    py_mult_to_mult_pass = PyMultToSquinMult(self)

    def run_pass(method):
        py_mult_to_mult_pass(method)

    return run_pass
