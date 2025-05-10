from kirin import ir
from kirin.passes import Fold, TypeInfer
from kirin.dialects import func, lowering

from .dialects import gate, noise, collapse, auxiliary


@ir.dialect_group(
    [noise, gate, auxiliary, collapse, func, lowering.func, lowering.call]
)
def main(self):
    typeinfer_pass = TypeInfer(self)
    fold_pass = Fold(self)

    def run_pass(
        mt: ir.Method,
        *,
        typeinfer: bool = False,
        fold: bool = True,
    ) -> None:

        if typeinfer:
            typeinfer_pass(mt)

        if fold:
            fold_pass(mt)

    return run_pass
