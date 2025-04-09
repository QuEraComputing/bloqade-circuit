# from typing import cast

from kirin import ir
from kirin.analysis import Forward
from kirin.analysis.forward import ForwardFrame

from bloqade.squin.op.types import OpType
from bloqade.squin.op.traits import Sized, HasSize

from .lattice import Shape, NoShape, OpShape


class ShapeAnalysis(Forward[Shape]):

    keys = ["op.shape"]
    lattice = Shape

    def initialize(self):
        super().initialize()
        return self

    # Take a page from const prop in Kirin,
    # I can get the data I want from the SizedTrait
    # and go from there

    ## This gets called before the registry look up
    def eval_stmt(self, frame: ForwardFrame, stmt: ir.Statement):
        method = self.lookup_registry(frame, stmt)
        if method is not None:
            return method(self, frame, stmt)
        elif stmt.has_trait(HasSize):
            has_size_inst = stmt.get_trait(HasSize)
            size = has_size_inst.get_size(stmt)
            return (OpShape(size=size),)
        elif stmt.has_trait(Sized):
            size = stmt.get_trait(Sized)
            return (OpShape(size=size.data),)
        else:
            return (NoShape(),)

    # For when no implementation is found for the statement
    def eval_stmt_fallback(
        self, frame: ForwardFrame[Shape], stmt: ir.Statement
    ) -> tuple[Shape, ...]:  # some form of Shape will go back into the frame
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
