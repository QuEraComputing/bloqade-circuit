from kirin import ir, passes
from kirin.dialects import func, ssacfg, lowering

from bloqade.qasm3.dialects import uop, core, expr


@ir.dialect_group([uop, expr, func, lowering.func, lowering.call, ssacfg])
def gate(self):
    fold_pass = passes.Fold(self)
    typeinfer_pass = passes.TypeInfer(self)

    def run_pass(
        method: ir.Method,
        *,
        fold: bool = True,
    ):
        method.verify()

        if isinstance(method.code, func.Function):
            new_code = expr.GateFunction(
                sym_name=method.code.sym_name,
                signature=method.code.signature,
                body=method.code.body,
            )
            method.code = new_code
        else:
            raise ValueError(
                "Gate Method code must be a Function, cannot be lambda/closure"
            )

        if fold:
            fold_pass(method)

        typeinfer_pass(method)
        method.verify_type()

    return run_pass


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
