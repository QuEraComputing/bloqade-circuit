from kirin import ir, interp
from kirin.analysis import Forward
from kirin.analysis.forward import ForwardFrame

from bloqade.squin.op.types import OpType

from .lattice import Shape


class ShapeAnalysis(Forward[Shape]):

    keys = ["op.shape"]
    lattice = Shape

    def initialize(self):
        super().initialize
        return self

    def eval_stmt_fallback(
        self, frame: ForwardFrame[Shape], stmt: ir.Statement
    ) -> tuple[Shape, ...] | interp.SpecialValue[Shape]:
        return tuple(
            (
                self.lattice.top()
                if result.type.is_subseteq(OpType)
                else self.lattice.bottom()
            )
            for result in stmt.results
        )

    def run_method(self, method: ir.Method, args: tuple[Shape, ...]):
        # NOTE: we do not support dynamic calls here, thus no need to propagate method object
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)
