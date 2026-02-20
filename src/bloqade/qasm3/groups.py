from kirin import ir, passes
from kirin.dialects import func, ssacfg, lowering

from bloqade.qasm3.dialects import uop, core, expr


@ir.dialect_group(
    [
        uop,
        expr,
        core,
        func,
        lowering.func,
        lowering.call,
        ssacfg,
    ]
)
def main(self):
    fold_pass = passes.Fold(self)
    typeinfer_pass = passes.TypeInfer(self)

    def run_pass(
        method: ir.Method,
        *,
        fold: bool = True,
    ):
        method.verify()

        if fold:
            fold_pass(method)

        typeinfer_pass(method)
        method.verify_type()

    return run_pass
