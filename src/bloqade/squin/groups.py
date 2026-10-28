from kirin import ir, passes
from kirin.prelude import structural_no_opt
from kirin.dialects import debug, ilist

from bloqade.decoders.dialects import annotate

from . import gate, noise
from .. import qubit
from ..qubit.passes import DesugarMeasurementBooleans


@ir.dialect_group(structural_no_opt.union([qubit, noise, gate, debug, annotate]))
def kernel(self):
    """Compile a function to a squin kernel.

    Runs the following passes on the method:

    1. Constant folding (if `fold=True`).
    2. Type inference (if `typeinfer=True`).
    3. Desugaring of ilist operations.
    4. Desugaring of boolean uses of measurement results, e.g. `m == 1`, `not m`,
       `m and n` or `if m:`, into `is_one` / `is_zero` / `is_lost` predicates.
    5. Type inference and type verification again (if `typeinfer=True`).

    Args:
        fold (bool): Fold constant expressions. Defaults to `True`.
        typeinfer (bool): Infer and verify types. Defaults to `True`.
    """
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
        DesugarMeasurementBooleans(method.dialects).fixpoint(method)

        if typeinfer:
            typeinfer_pass(method)  # fix types after desugaring
            method.verify_type()

    return run_pass
