from kirin import ir, passes
from kirin.prelude import structural_no_opt
from kirin.dialects import debug, ilist

from bloqade.decoders.dialects import annotate

from . import gate, noise
from .. import qubit


@ir.dialect_group(structural_no_opt.union([qubit, noise, gate, debug, annotate]))
def kernel(self):
    fold_pass = passes.Fold(self)
    typeinfer_pass = passes.TypeInfer(self)
    ilist_desugar_pass = ilist.IListDesugar(self)

    def run_pass(method: ir.Method, *, fold=True, typeinfer=True):
        method.verify()
        if fold:
            fold_pass.fixpoint(method)

        if typeinfer:
            typeinfer_pass(method)  # infer types before desugaring

        ilist_desugar_pass(method)

        if typeinfer:
            typeinfer_pass(method)  # fix types after desugaring
            method.verify_type()

    return run_pass
